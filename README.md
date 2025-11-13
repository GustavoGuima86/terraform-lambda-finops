# FinOps Lambda Reporter

This project provides a comprehensive FinOps report by deploying an AWS Lambda function that gathers data from various AWS services. The collected data is then presented in a JSON format, offering insights into costs, usage, and optimization opportunities.

## Features

The Lambda function collects data from the following AWS services:

-   **AWS Cost Explorer:**
    -   Reservation utilization over the last six months.
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

## Deployment

This project uses Terraform to manage and deploy the necessary AWS infrastructure.

### Prerequisites

-   [Terraform](https://learn.hashicorp.com/tutorials/terraform/install-cli) installed.
-   AWS credentials configured for Terraform.

### Steps

1.  **Initialize Terraform:**
    Open a terminal in the project's root directory and run:
    ```bash
    terraform init
    ```

2.  **Deploy the Infrastructure:**
    Apply the Terraform configuration to deploy the Lambda function and related resources:
    ```bash
    terraform apply
    ```
    Terraform will show you a plan of the resources to be created. Type `yes` to confirm.

3.  **Access the Report:**
    Once the deployment is complete, the Lambda function will be invoked, and the FinOps report will be saved as `report.json` in the root directory.

### Updating the Lambda Function

If you make changes to the `lambda/lambda_function.py` file, you'll need to redeploy the function:

1.  **Create a new zip file:**
    ```bash
    zip -j lambda.zip lambda/lambda_function.py
    ```

2.  **Redeploy with Terraform:**
    ```bash
    terraform apply
    ```
