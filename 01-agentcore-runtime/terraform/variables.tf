variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "runtime_name" {
  type        = string
  default     = "calc_agent_terraform"
  description = "Must match ^[a-zA-Z][a-zA-Z0-9_]{0,47}$"
}

variable "ecr_repository_name" {
  type    = string
  default = "bedrock-agentcore-calc-agent-terraform"
}

variable "image_tag" {
  type    = string
  default = "latest"
}
