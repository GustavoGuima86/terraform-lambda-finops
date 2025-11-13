# FinOps Lambda Reporter

This project provides a comprehensive FinOps report by deploying an AWS Lambda function that gathers data from various AWS services. The collected data is then presented in a JSON format, offering insights into costs, usage, and optimization opportunities.

## Features

The Lambda function collects data from the following AWS services:

-   **AWS Cost Explorer:**
    -   Reservation utilization over the last six months.
    -   Savings Plans coverage and utilization over the last six months.
    -   Monthly cost and usage data, filtered for services with costs exceeding $10.
-   **Amazon EC2:**
    -   List of running instances with their descriptions and average CPU utilization.
    -   Compute Optimizer recommendations for EC2 instances.
-   **Amazon EBS:**
    -   Details of all EBS volumes, including type, size, and usage status.
    -   Information on all EBS snapshots, including their associated volume size and lifecycle policy.
-   **Amazon S3:**
    -   Data for each S3 bucket, including storage usage, lifecycle policies, and tiering information.
-   **Amazon VPC:**
    -   Network topology, including VPCs, subnets, internet gateways, and NAT gateways.
    -   Identification of underutilized NAT gateways.
-   **Amazon EKS:**
    -   Information on EKS clusters, including nodes and whether they use Karpenter for autoscaling.
-   **Amazon RDS:**
    -   Data on RDS instances, including CPU utilization and snapshot details.
-   **Amazon DynamoDB:**
    -   Information on DynamoDB tables, including capacity usage and backup status.
-   **Amazon ElastiCache:**
    -   Details of ElastiCache clusters, including CPU and memory utilization.
-   **Amazon EFS:**
    -   Data on EFS file systems, including size, usage, and backup policies.
-   **AWS Elastic Load Balancing:**
    -   Information on load balancers and their associated target groups.
-   **Amazon CloudWatch Logs:**
    -   Details of CloudWatch log groups, including stored data size and retention policies.
-   **AWS Lambda:**
    -   Information on Lambda functions, including memory allocation and average usage.
-   **Amazon OpenSearch Service:**
    -   Data on OpenSearch domains, including instance types and storage sizes.
-   **Amazon Kinesis:**
    -   Information on Kinesis data streams.
-   **Amazon SQS:**
    -   Details of SQS queues.
-   **Amazon SNS:**
    -   Information on SNS topics.
-   **Amazon EC2 (EIP):**
    -   List of unused Elastic IP addresses.
-   **AWS Data Transfer:**
    -   Aggregated data transfer costs.
-   **Amazon CloudFront:**
    -   Details of CloudFront distributions, including cache behaviors and usage metrics.

## Report Structure

The `report.json` file will have the following structure:

```json
{
  "cost_and_usage": {
    "Amazon Elastic Compute Cloud - Compute": {
      "monthly_expenses": {
        "2025/05": 150.75
      },
      "total_cost": 150.75,
      "average_cost": 150.75
    }
  },
  "savings": {
    "reservation_utilization": [],
    "savings_plans_coverage": [],
    "savings_plans_utilization": []
  },
  "computing": {
    "ec2_instances": [
      {
        "InstanceId": "i-0123456789abcdef0",
        "Description": "My EC2 Instance",
        "AverageCPUUtilization": "10.50%"
      }
    ],
    "eks_data": [],
    "lambda_functions": [],
    "elasticsearch_data": []
  },
  "storage": {
    "ebs_volumes": [],
    "ebs_snapshots": [],
    "s3_data": [],
    "efs_data": []
  },
  "databases": {
    "rds_data": [],
    "dynamodb_data": [],
    "elasticache_data": []
  },
  "networking": {
    "network_topology": [],
    "lost_nat_gateways": [],
    "unused_eips": [],
    "data_transfer_costs": [],
    "cloudfront_data": [],
    "load_balancers": []
  },
  "others": {
    "cloudwatch_logs": [],
    "kinesis_data": [],
    "sqs_data": [],
    "sns_data": []
  }
}
```
