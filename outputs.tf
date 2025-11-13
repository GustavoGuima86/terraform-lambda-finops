output "lambda_function_name" {
  description = "The name of the FinOps Lambda function."
  value       = aws_lambda_function.finops_lambda.function_name
}

output "lambda_function_arn" {
  description = "The ARN of the FinOps Lambda function."
  value       = aws_lambda_function.finops_lambda.arn
}

output "iam_role_name" {
  description = "The name of the IAM role for the Lambda function."
  value       = aws_iam_role.lambda_exec_role.name
}
