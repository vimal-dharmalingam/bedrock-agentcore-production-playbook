output "public_ip" {
  value = aws_instance.calc_agent.public_ip
}

output "invoke_url" {
  value = "http://${aws_instance.calc_agent.public_ip}:${var.app_port}/invoke"
}
