
provider "aws" {
  region = var.aws_region
}

resource "aws_iam_role" "lambda_exec_role" {
  name = "lambda_finops_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "lambda_finops_policy"
  description = "Policy for FinOps Lambda function"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "ce:GetCostAndUsage",
          "ce:GetReservationUtilization",
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "dlm:GetLifecyclePolicies",
          "dynamodb:DescribeContinuousBackups",
          "dynamodb:DescribeTable",
          "dynamodb:ListBackups",
          "dynamodb:ListTables",
          "ec2:DescribeInstances",
          "ec2:DescribeInternetGateways",
          "ec2:DescribeNatGateways",
          "ec2:DescribeRouteTables",
          "ec2:DescribeSnapshots",
          "ec2:DescribeSubnets",
          "ec2:DescribeTransitGateways",
          "ec2:DescribeVolumes",
          "ec2:DescribeVpcs",
          "elasticfilesystem:DescribeFileSystems",
          "efs:DescribeBackupPolicy",
          "efs:DescribeMountTargets",
          "eks:DescribeCluster",
          "eks:DescribeNodegroup",
          "eks:ListClusters",
          "eks:ListNodegroups",
          "elasticache:DescribeCacheClusters",
          "elasticache:DescribeSnapshots",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeTargetGroups",
          "elasticloadbalancing:DescribeTargetHealth",
          "es:ListDomainNames",
          "lambda:ListFunctions",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "rds:DescribeDBInstances",
          "rds:DescribeDBSnapshots",
          "s3:GetBucketLifecycleConfiguration",
          "s3:GetLifecycleConfiguration",
          "s3:ListAllMyBuckets",
          "s3:ListBuckets",
          "logs:FilterLogEvents",
          "compute-optimizer:GetEC2InstanceRecommendations",
          "sts:GetCallerIdentity",
          "opensearch:ListDomainNames",
          "opensearch:DescribeDomain",
          "kinesis:ListStreams",
          "kinesis:DescribeStream",
          "sqs:ListQueues",
          "sqs:GetQueueAttributes",
          "sns:ListTopics",
          "sns:GetTopicAttributes",
          "ec2:DescribeAddresses",
          "cloudfront:ListDistributions",
          "cloudfront:GetDistributionConfig"
        ],
        Resource = "*"
      },
      {
        Effect   = "Allow",
        Action   = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda.zip"
}

resource "aws_lambda_function" "finops_lambda" {
  function_name = "finops_data_collector"
  role          = aws_iam_role.lambda_exec_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.9"
  filename      = data.archive_file.lambda_zip.output_path
  timeout = 300
  memory_size = 1024
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      LOG_LEVEL = "INFO"
    }
  }
}

resource "aws_cloudwatch_event_rule" "daily_trigger" {
  name                = "daily_finops_lambda_trigger"
  description         = "Trigger FinOps Lambda daily"
  schedule_expression = "rate(1 day)"
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.daily_trigger.name
  target_id = "finops_lambda"
  arn       = aws_lambda_function.finops_lambda.arn
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.finops_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_trigger.arn
}
