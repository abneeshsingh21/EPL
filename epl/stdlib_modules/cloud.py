"""
EPL Cloud Domain — stdlib module facade for AWS cloud functions.

Provides function names, documentation strings, and metadata for the
cloud_* standard library functions used by autocompletion, help, and LSP.
"""

from __future__ import annotations

FUNCTIONS = frozenset(
    {
        'cloud_configure',
        'cloud_s3_upload',
        'cloud_s3_download',
        'cloud_s3_list',
        'cloud_s3_delete',
        'cloud_s3_exists',
        'cloud_s3_read_text',
        'cloud_s3_write_text',
        'cloud_s3_create_bucket',
        'cloud_s3_list_buckets',
        'cloud_lambda_invoke',
        'cloud_sqs_send',
        'cloud_sqs_receive',
        'cloud_sqs_delete',
    }
)

DOCS = {
    # Configuration
    'cloud_configure': 'Configure AWS region and credentials (region[, access_key, secret_key]).',
    # S3 — Object operations
    'cloud_s3_upload': 'Upload a local file to an S3 bucket (bucket, key, file_path).',
    'cloud_s3_download': 'Download an S3 object to a local file (bucket, key, file_path).',
    'cloud_s3_list': 'List objects in an S3 bucket, optionally filtered by prefix (bucket[, prefix]).',
    'cloud_s3_delete': 'Delete an object from an S3 bucket (bucket, key).',
    'cloud_s3_exists': 'Check whether an object exists in S3 (bucket, key). Returns True/False.',
    'cloud_s3_read_text': 'Read a text object from S3 directly into a string (bucket, key[, encoding]).',
    'cloud_s3_write_text': 'Write a string directly to an S3 object (bucket, key, content).',
    # S3 — Bucket operations
    'cloud_s3_create_bucket': 'Create a new S3 bucket (bucket).',
    'cloud_s3_list_buckets': 'List all S3 buckets in the account.',
    # Lambda
    'cloud_lambda_invoke': 'Invoke an AWS Lambda function (function_name[, payload]).',
    # SQS
    'cloud_sqs_send': 'Send a message to an SQS queue (queue_url, message).',
    'cloud_sqs_receive': 'Receive messages from an SQS queue (queue_url[, max_messages]).',
    'cloud_sqs_delete': 'Delete (acknowledge) a message from an SQS queue (queue_url, receipt_handle).',
}


def get_functions() -> frozenset[str]:
    return FUNCTIONS


def describe(fn_name: str) -> str:
    return DOCS.get(fn_name, f'{fn_name}: no documentation available.')
