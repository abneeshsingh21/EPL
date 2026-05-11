"""
EPL Cloud Backend — AWS S3, Lambda, and SQS integration.

Provides cloud infrastructure operations for the EPL language using
boto3 under the hood. boto3 is lazily imported so the module is safe
to load even when the dependency is absent; a clear error is raised
only when a cloud function is actually invoked without boto3 installed.

Environment variables used by boto3 for authentication:
    AWS_ACCESS_KEY_ID      — AWS access key
    AWS_SECRET_ACCESS_KEY  — AWS secret key
    AWS_DEFAULT_REGION     — AWS region (default: us-east-1)

EPL users may also call cloud_configure(region, key, secret) to set
credentials programmatically.
"""

from __future__ import annotations

import logging as _logging
import os as _os
import threading as _threading

from epl.errors import RuntimeError as EPLRuntimeError

_log = _logging.getLogger(__name__)

# ─── Lazy boto3 import ────────────────────────────────────

_boto3 = None
_boto3_lock = _threading.Lock()


def _ensure_boto3():
    """Lazily import boto3, raising a helpful error if missing."""
    global _boto3
    if _boto3 is not None:
        return _boto3
    with _boto3_lock:
        if _boto3 is not None:
            return _boto3
        try:
            import boto3

            _boto3 = boto3
            return _boto3
        except ImportError:
            raise EPLRuntimeError(
                'Cloud functions require the boto3 package. '
                'Install with: pip install "eplang[cloud]"  or  pip install boto3',
                0,
            )


# ─── Internal client cache ────────────────────────────────

_clients = {}  # service_name -> boto3.client
_client_lock = _threading.Lock()
_config = {
    'region': _os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
    'access_key': None,  # None = defer to env / instance role
    'secret_key': None,
}


def _get_client(service: str):
    """Return a cached boto3 client for the given AWS service."""
    if service in _clients:
        return _clients[service]
    with _client_lock:
        if service in _clients:
            return _clients[service]
        boto3 = _ensure_boto3()
        kwargs = {'region_name': _config['region']}
        if _config['access_key'] and _config['secret_key']:
            kwargs['aws_access_key_id'] = _config['access_key']
            kwargs['aws_secret_access_key'] = _config['secret_key']
        client = boto3.client(service, **kwargs)
        _clients[service] = client
        return client


def _invalidate_clients():
    """Clear cached clients (called after cloud_configure)."""
    with _client_lock:
        _clients.clear()


# ═══════════════════════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════════════════════


def cloud_configure(region=None, access_key=None, secret_key=None):
    """Configure AWS credentials and region programmatically."""
    if region is not None:
        _config['region'] = str(region)
    if access_key is not None:
        _config['access_key'] = str(access_key)
    if secret_key is not None:
        _config['secret_key'] = str(secret_key)
    _invalidate_clients()
    return True


# ═══════════════════════════════════════════════════════════
#  S3 — Object Storage
# ═══════════════════════════════════════════════════════════


def cloud_s3_upload(bucket: str, key: str, file_path: str):
    """Upload a local file to an S3 bucket."""
    s3 = _get_client('s3')
    s3.upload_file(str(file_path), str(bucket), str(key))
    return {'bucket': str(bucket), 'key': str(key), 'status': 'uploaded'}


def cloud_s3_download(bucket: str, key: str, file_path: str):
    """Download an object from S3 to a local file."""
    s3 = _get_client('s3')
    s3.download_file(str(bucket), str(key), str(file_path))
    return {
        'bucket': str(bucket),
        'key': str(key),
        'file_path': str(file_path),
        'status': 'downloaded',
    }


def cloud_s3_list(bucket: str, prefix: str = ''):
    """List objects in an S3 bucket, optionally filtered by prefix."""
    s3 = _get_client('s3')
    kwargs = {'Bucket': str(bucket)}
    if prefix:
        kwargs['Prefix'] = str(prefix)
    results = []
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(**kwargs):
        for obj in page.get('Contents', []):
            results.append(
                {
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                }
            )
    return results


def cloud_s3_delete(bucket: str, key: str):
    """Delete an object from an S3 bucket."""
    s3 = _get_client('s3')
    s3.delete_object(Bucket=str(bucket), Key=str(key))
    return {'bucket': str(bucket), 'key': str(key), 'status': 'deleted'}


def cloud_s3_exists(bucket: str, key: str):
    """Check whether an object exists in S3."""
    s3 = _get_client('s3')
    try:
        s3.head_object(Bucket=str(bucket), Key=str(key))
        return True
    except Exception:
        return False


def cloud_s3_read_text(bucket: str, key: str, encoding: str = 'utf-8'):
    """Read a text object from S3 directly into a string."""
    s3 = _get_client('s3')
    response = s3.get_object(Bucket=str(bucket), Key=str(key))
    body = response['Body'].read()
    return body.decode(str(encoding))


def cloud_s3_write_text(bucket: str, key: str, content: str):
    """Write a string directly to an S3 object."""
    s3 = _get_client('s3')
    s3.put_object(
        Bucket=str(bucket),
        Key=str(key),
        Body=str(content).encode('utf-8'),
        ContentType='text/plain; charset=utf-8',
    )
    return {'bucket': str(bucket), 'key': str(key), 'status': 'written'}


# ═══════════════════════════════════════════════════════════
#  S3 — Bucket Operations
# ═══════════════════════════════════════════════════════════


def cloud_s3_create_bucket(bucket: str):
    """Create a new S3 bucket."""
    s3 = _get_client('s3')
    create_kwargs = {'Bucket': str(bucket)}
    region = _config['region']
    if region and region != 'us-east-1':
        create_kwargs['CreateBucketConfiguration'] = {'LocationConstraint': region}
    s3.create_bucket(**create_kwargs)
    return {'bucket': str(bucket), 'status': 'created'}


def cloud_s3_list_buckets():
    """List all S3 buckets in the account."""
    s3 = _get_client('s3')
    response = s3.list_buckets()
    return [
        {'name': b['Name'], 'creation_date': b['CreationDate'].isoformat()}
        for b in response.get('Buckets', [])
    ]


# ═══════════════════════════════════════════════════════════
#  Lambda — Serverless Functions
# ═══════════════════════════════════════════════════════════


def cloud_lambda_invoke(function_name: str, payload=None):
    """Invoke an AWS Lambda function."""
    import json as _json

    lam = _get_client('lambda')
    invoke_kwargs = {
        'FunctionName': str(function_name),
        'InvocationType': 'RequestResponse',
    }
    if payload is not None:
        if isinstance(payload, str):
            invoke_kwargs['Payload'] = payload
        else:
            invoke_kwargs['Payload'] = _json.dumps(payload)
    response = lam.invoke(**invoke_kwargs)
    resp_payload = response['Payload'].read().decode('utf-8')
    try:
        resp_payload = _json.loads(resp_payload)
    except (ValueError, _json.JSONDecodeError):
        pass
    return {
        'status_code': response['StatusCode'],
        'payload': resp_payload,
        'function_error': response.get('FunctionError'),
    }


# ═══════════════════════════════════════════════════════════
#  SQS — Message Queues
# ═══════════════════════════════════════════════════════════


def cloud_sqs_send(queue_url: str, message: str):
    """Send a message to an SQS queue."""
    sqs = _get_client('sqs')
    response = sqs.send_message(QueueUrl=str(queue_url), MessageBody=str(message))
    return {'message_id': response['MessageId'], 'status': 'sent'}


def cloud_sqs_receive(queue_url: str, max_messages: int = 1):
    """Receive messages from an SQS queue."""
    sqs = _get_client('sqs')
    response = sqs.receive_message(
        QueueUrl=str(queue_url),
        MaxNumberOfMessages=int(max_messages),
    )
    return [
        {
            'message_id': msg['MessageId'],
            'body': msg['Body'],
            'receipt_handle': msg['ReceiptHandle'],
        }
        for msg in response.get('Messages', [])
    ]


def cloud_sqs_delete(queue_url: str, receipt_handle: str):
    """Delete a message from an SQS queue (acknowledge receipt)."""
    sqs = _get_client('sqs')
    sqs.delete_message(QueueUrl=str(queue_url), ReceiptHandle=str(receipt_handle))
    return {'status': 'deleted'}
