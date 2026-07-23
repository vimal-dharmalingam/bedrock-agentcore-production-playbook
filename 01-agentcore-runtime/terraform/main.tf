# Fully self-contained: this file creates its own ECR repo, its own IAM role/policy, and
# the AgentCore Runtime resource itself. No dependency on any other 01-agentcore-runtime
# sub-method's AWS resources.
#
# Confirmed via the Terraform Registry docs before writing any of this: aws_bedrockagentcore_agent_runtime
# is a native resource in hashicorp/aws (not the awscc/Cloud-Control-API provider) -- a real,
# hand-maintained Terraform resource, not just an auto-generated CloudFormation wrapper.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ---------------------------------------------------------------------------
# ECR repository -- Terraform CAN manage this as a resource (it's just an empty
# repository, no image content involved), unlike the image itself, which Terraform
# cannot build. Same "orchestrate, don't construct" lesson as the cloudformation module.
# ---------------------------------------------------------------------------
resource "aws_ecr_repository" "calc_agent" {
  name = var.ecr_repository_name
}

# ---------------------------------------------------------------------------
# Execution role -- same trust policy shape as every other module, expressed via
# Terraform's aws_iam_policy_document data source instead of raw JSON. This is the
# idiomatic Terraform way to author IAM policies (still compiles to the same JSON
# under the hood, but with HCL syntax checking and interpolation).
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:runtime/${var.runtime_name}*"]
    }
  }
}

resource "aws_iam_role" "execution_role" {
  # Explicit name matching the *BedrockAgentCore* pattern already granted by earlier IAM
  # policies -- same lesson learned the hard way in the cloudformation module: an
  # auto-generated name here would cause an AccessDenied that has nothing to do with
  # Terraform itself.
  name               = "BedrockAgentCoreTerraformExecutionRole"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

# Same permission set as every other module's execution policy (logs, X-Ray, CloudWatch,
# bedrock:InvokeModel, ECR pull) -- no L2-construct-style auto-generation here either,
# same as cloudformation, every statement explicit.
data "aws_iam_policy_document" "execution_permissions" {
  statement {
    sid       = "LogGroupAccess"
    effect    = "Allow"
    actions   = ["logs:DescribeLogStreams", "logs:CreateLogGroup"]
    resources = ["arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"]
  }

  statement {
    sid       = "DescribeLogGroups"
    effect    = "Allow"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:*"]
  }

  statement {
    sid       = "LogStreamAccess"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"]
  }

  statement {
    sid       = "XRayAccess"
    effect    = "Allow"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"]
    resources = ["*"]
  }

  statement {
    sid       = "CloudWatchMetrics"
    effect    = "Allow"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }

  statement {
    sid     = "BedrockModelInvocation"
    effect  = "Allow"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:aws:bedrock:*::foundation-model/*",
      "arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*",
    ]
  }

  statement {
    sid       = "ECRImagePull"
    effect    = "Allow"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
    resources = [aws_ecr_repository.calc_agent.arn]
  }

  statement {
    sid       = "ECRAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "execution_policy" {
  name   = "TerraformExecutionPolicy"
  role   = aws_iam_role.execution_role.id
  policy = data.aws_iam_policy_document.execution_permissions.json
}

# ---------------------------------------------------------------------------
# The actual runtime. container_uri references the ECR repo Terraform just created --
# but the IMAGE at that URI has to already be pushed by hand (docker build/push, see
# README) before this resource can be created. Terraform builds the repo, not the image.
# ---------------------------------------------------------------------------
resource "aws_bedrockagentcore_agent_runtime" "calc_agent" {
  agent_runtime_name = var.runtime_name
  role_arn            = aws_iam_role.execution_role.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.calc_agent.repository_url}:${var.image_tag}"
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  depends_on = [aws_iam_role_policy.execution_policy]
}
