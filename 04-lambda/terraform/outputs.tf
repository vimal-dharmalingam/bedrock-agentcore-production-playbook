output "function_arn" {
  value = aws_lambda_function.calc_agent.arn
}

output "function_name" {
  value = aws_lambda_function.calc_agent.function_name
}
