# Same calculator agent as zip-deploy/, deployed via hashicorp/aws instead of raw boto3.
# Much simpler than 01-agentcore-runtime/terraform: no ECR chicken-and-egg problem, since
# Lambda's zip deployment just needs a local zip file, not a container registry.

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
data "aws_region" "current" {}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_execution_role" {
  # Deliberately named to match the *already-granted* "role/CalcAgentLambda*" pattern from
  # 03-classic-bedrock-agent-lambda's IAM policy -- same lesson as every naming choice
  # tonight: pick a name that fits an existing wildcard grant and a whole class of new
  # permission gaps just doesn't happen.
  name               = "CalcAgentLambdaTerraformExecutionRole"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

data "aws_iam_policy_document" "execution_permissions" {
  statement {
    sid       = "LambdaBasicExecution"
    effect    = "Allow"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.function_name}*"]
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
}

resource "aws_iam_role_policy" "execution_policy" {
  name   = "TerraformLambdaExecutionPolicy"
  role   = aws_iam_role.lambda_execution_role.id
  policy = data.aws_iam_policy_document.execution_permissions.json
}

resource "aws_lambda_function" "calc_agent" {
  function_name    = var.function_name
  role             = aws_iam_role.lambda_execution_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.13"
  architectures    = ["x86_64"]
  timeout          = 30
  memory_size      = 512

  # Points directly at the zip built by build_lambda_package.py -- no archive_file provider
  # needed, since dependency installation (uv, platform-specific wheels) has to happen
  # outside Terraform anyway.
  filename         = "${path.module}/deployment_package.zip"
  source_code_hash = filebase64sha256("${path.module}/deployment_package.zip")

  depends_on = [aws_iam_role_policy.execution_policy]
}
