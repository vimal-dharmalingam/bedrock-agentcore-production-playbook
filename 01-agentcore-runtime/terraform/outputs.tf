output "ecr_repository_url" {
  description = "Push your image here before running `terraform apply` a second time"
  value       = aws_ecr_repository.calc_agent.repository_url
}

output "agent_runtime_id" {
  description = "Use this to invoke the agent"
  value       = aws_bedrockagentcore_agent_runtime.calc_agent.agent_runtime_id
}

output "agent_runtime_arn" {
  value = aws_bedrockagentcore_agent_runtime.calc_agent.agent_runtime_arn
}
