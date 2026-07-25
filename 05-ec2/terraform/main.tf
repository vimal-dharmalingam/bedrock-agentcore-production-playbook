# Calculator agent hosted on a raw EC2 instance -- no managed invoke API in front of it, unlike
# every prior module. Terraform's job here is standard IaaS provisioning: AMI selection, a
# security group, an IAM role + instance profile, and a user-data bootstrap script -- a
# genuinely different shape of work than AgentCore Runtime or Lambda, where Terraform mostly
# pointed at an artifact someone else already built (a container image, a zip).

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

# Latest Amazon Linux 2023 AMI -- resolved at plan/apply time, not hardcoded, so this module
# doesn't go stale as AWS rotates AMI IDs.
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Default VPC / default public subnet -- simplest possible networking for a portfolio module.
# A real deployment would use a purpose-built VPC with private subnets behind a NAT gateway or
# ALB, not a public IP directly on the instance.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "calc_agent" {
  name        = "CalcAgentEc2SecurityGroup"
  description = "Allow inbound only to the calculator agent app port. No SSH port opened at all."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Agent HTTP API"
    from_port   = var.app_port
    to_port     = var.app_port
    protocol    = "tcp"
    cidr_blocks = [var.ingress_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2_role" {
  # Named to match the already-granted "role/CalcAgent*" wildcard pattern used in every prior
  # module -- avoids a fresh IAM-role-name gap, same trick as cdk/, terraform/, cloudformation/
  # in 04-lambda.
  name               = "CalcAgentEc2ExecutionRole"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

data "aws_iam_policy_document" "ec2_permissions" {
  statement {
    sid     = "BedrockModelInvocation"
    effect  = "Allow"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:aws:bedrock:*::foundation-model/*",
      "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*",
    ]
  }
}

resource "aws_iam_role_policy" "ec2_policy" {
  name   = "CalcAgentEc2Policy"
  role   = aws_iam_role.ec2_role.id
  policy = data.aws_iam_policy_document.ec2_permissions.json
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "CalcAgentEc2InstanceProfile"
  role = aws_iam_role.ec2_role.name
}

resource "aws_instance" "calc_agent" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.instance_type
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.calc_agent.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2_profile.name
  associate_public_ip_address = true

  # User-data only executes once, at first boot, via cloud-init -- changing it on a running
  # instance and letting the provider do an in-place stop/modify/start (its default behavior)
  # does NOT re-run the script. Forcing a full replace on every user_data change is what
  # actually gets a changed boot script to execute -- learned this the hard way when a fix
  # "applied successfully" but the instance kept running its old, broken boot state.
  user_data_replace_on_change = true

  # Agent code and its requirements.txt are embedded directly in user-data via templatefile()
  # -- small enough (well under user-data's ~16KB limit) that no S3 upload step is needed at
  # all, unlike 04-lambda/cloudformation's zip-via-S3 approach.
  #
  # The outer replace() strips \r from the whole rendered script. Root cause hit in testing:
  # files authored/edited on Windows can carry CRLF line endings, which makes bash heredoc
  # terminator lines (PYEOF/REQEOF/SVCEOF) read as e.g. "PYEOF\r" -- that doesn't match the
  # literal delimiter "PYEOF", so the heredoc never closes where it should and bash starts
  # trying to *execute* raw Python docstring text as shell commands ("FastAPI: command not
  # found"). Normalizing to LF here, after templatefile() has already substituted everything,
  # covers CRLF from any source (the .tpl file itself or the injected app.py/requirements.txt).
  user_data = replace(
    templatefile("${path.module}/user_data.sh.tpl", {
      app_py_content       = file("${path.module}/app.py")
      requirements_content = file("${path.module}/requirements.txt")
      app_port              = var.app_port
      aws_region             = var.aws_region
    }),
    "\r\n", "\n"
  )

  tags = {
    Name = "calc-agent-ec2"
  }
}
