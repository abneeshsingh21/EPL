# epl-cloud

AWS cloud integration for EPL — upload files to S3, invoke Lambda functions,
and send/receive SQS messages, all in plain English syntax.

## Install

```bash
epl use epl-cloud
pip install "eplang[cloud]"
```

> **Note:** This package requires AWS credentials. Set the environment variables
> `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optionally `AWS_DEFAULT_REGION`,
> or call `cloud_configure()` in your EPL program.

## Quick Start

```epl
Use "epl-cloud"

Note: Configure AWS region
Call configure("us-west-2")

Note: Upload a file to S3
result = upload("my-bucket", "data/report.csv", "report.csv")
Say result

Note: List files in a bucket
files = list_objects("my-bucket", "data/")
For Each file in files
    Say file
End

Note: Read text directly from S3
content = read_text("my-bucket", "config.json")
Say content
```

## Included Surface

### Configuration
- `configure(region, access_key, secret_key)` — Set AWS credentials

### S3 — Object Storage
- `upload(bucket, key, file_path)` — Upload a file
- `download(bucket, key, file_path)` — Download a file
- `list_objects(bucket, prefix)` — List objects
- `delete_object(bucket, key)` — Delete an object
- `exists(bucket, key)` — Check if an object exists
- `read_text(bucket, key)` — Read text from S3
- `write_text(bucket, key, content)` — Write text to S3
- `create_bucket(bucket)` — Create a new bucket
- `list_buckets()` — List all buckets

### Lambda — Serverless Functions
- `invoke_function(function_name, payload)` — Invoke a Lambda function

### SQS — Message Queues
- `send_message(queue_url, message)` — Send a message
- `receive_messages(queue_url, max_messages)` — Receive messages
- `delete_message(queue_url, receipt_handle)` — Acknowledge a message
