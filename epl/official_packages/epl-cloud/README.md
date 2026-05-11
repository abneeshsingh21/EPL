# epl-cloud

AWS cloud integration for EPL — upload/download files to S3, invoke Lambda
functions, and send/receive SQS messages, all in plain English.

## Installation

```bash
pip install "eplang[cloud]"
```

## Quick Start

```epl
Note: Configure AWS credentials
Call cloud_configure("us-east-1")

Note: Upload a file to S3
Call cloud_s3_upload("my-bucket", "data/report.csv", "report.csv")

Note: Invoke a Lambda function
Create result equal to cloud_lambda_invoke("my-function", Map with key = "value")
Say result.payload

Note: Send an SQS message
Call cloud_sqs_send("https://sqs.us-east-1.amazonaws.com/123/my-queue", "Hello from EPL!")
```
