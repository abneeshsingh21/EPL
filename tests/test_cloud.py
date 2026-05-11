"""Tests for the epl-cloud package (PR #4).

Covers:
1. Module structure — cloud domain registration
2. Backend unit tests — cloud_backend.py with mocked boto3
3. Stdlib dispatch — call_stdlib routes cloud_* correctly
4. pyproject.toml integration
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════
#  1. Module structure tests
# ═══════════════════════════════════════════════════════════


class TestCloudModuleStructure(unittest.TestCase):
    """Verify the cloud domain is registered across all layers."""

    def test_cloud_functions_in_stdlib_functions_set(self):
        from epl.stdlib import STDLIB_FUNCTIONS

        expected = {
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
        self.assertTrue(
            expected.issubset(STDLIB_FUNCTIONS), f'Missing: {expected - STDLIB_FUNCTIONS}'
        )

    def test_cloud_domain_in_domain_map(self):
        from epl.stdlib_modules import DOMAIN_MAP

        self.assertIn('cloud', DOMAIN_MAP)
        self.assertIn('cloud_s3_upload', DOMAIN_MAP['cloud'])
        self.assertIn('cloud_lambda_invoke', DOMAIN_MAP['cloud'])
        self.assertIn('cloud_sqs_send', DOMAIN_MAP['cloud'])

    def test_cloud_domain_reverse_lookup(self):
        from epl.stdlib_modules import get_domain

        self.assertEqual(get_domain('cloud_s3_upload'), 'cloud')
        self.assertEqual(get_domain('cloud_lambda_invoke'), 'cloud')
        self.assertEqual(get_domain('cloud_sqs_send'), 'cloud')

    def test_cloud_stdlib_module_facade(self):
        from epl.stdlib_modules.cloud import DOCS, FUNCTIONS, describe, get_functions

        self.assertIn('cloud_s3_upload', FUNCTIONS)
        self.assertIn('cloud_s3_upload', DOCS)
        self.assertEqual(FUNCTIONS, get_functions())
        doc = describe('cloud_s3_upload')
        self.assertIn('Upload', doc)

    def test_cloud_in_registry_json(self):
        import json

        registry_path = REPO_ROOT / 'epl' / 'registry.json'
        registry = json.loads(registry_path.read_text(encoding='utf-8'))
        self.assertIn('epl-cloud', registry['packages'])
        pkg = registry['packages']['epl-cloud']
        self.assertEqual(pkg['version'], '1.0.0')
        self.assertIn('s3', pkg['keywords'])

    def test_official_package_files_exist(self):
        pkg_root = REPO_ROOT / 'epl' / 'official_packages' / 'epl-cloud'
        self.assertTrue((pkg_root / 'epl.toml').is_file())
        self.assertTrue((pkg_root / 'README.md').is_file())
        self.assertTrue((pkg_root / 'src' / 'main.epl').is_file())
        self.assertTrue((pkg_root / 'examples' / 'basic.epl').is_file())

    def test_epl_source_parses(self):
        from epl.lexer import Lexer
        from epl.parser import Parser

        pkg_root = REPO_ROOT / 'epl' / 'official_packages' / 'epl-cloud'
        for epl_file in [pkg_root / 'src' / 'main.epl', pkg_root / 'examples' / 'basic.epl']:
            with self.subTest(file=epl_file.name):
                source = epl_file.read_text(encoding='utf-8')
                tokens = Lexer(source).tokenize()
                Parser(tokens).parse()  # should not raise


# ═══════════════════════════════════════════════════════════
#  2. Backend unit tests (mocked boto3)
# ═══════════════════════════════════════════════════════════


class TestCloudBackend(unittest.TestCase):
    """Test cloud_backend.py functions with mocked boto3 clients."""

    def setUp(self):
        from epl import cloud_backend

        cloud_backend._clients.clear()
        cloud_backend._boto3 = None

    def _mock_boto3(self):
        from epl import cloud_backend

        mock_boto3 = MagicMock()
        cloud_backend._boto3 = mock_boto3
        return mock_boto3

    def test_configure_updates_region(self):
        from epl import cloud_backend

        cloud_backend.cloud_configure(region='eu-west-1')
        self.assertEqual(cloud_backend._config['region'], 'eu-west-1')
        cloud_backend.cloud_configure(region='us-east-1')

    def test_configure_invalidates_clients(self):
        from epl import cloud_backend

        self._mock_boto3()
        cloud_backend._get_client('s3')
        self.assertIn('s3', cloud_backend._clients)
        cloud_backend.cloud_configure(region='ap-south-1')
        self.assertEqual(len(cloud_backend._clients), 0)
        cloud_backend.cloud_configure(region='us-east-1')

    def test_s3_upload_calls_boto3(self):
        from epl import cloud_backend

        mock_boto3 = self._mock_boto3()
        mock_s3 = mock_boto3.client.return_value
        result = cloud_backend.cloud_s3_upload('my-bucket', 'key.txt', '/tmp/file.txt')
        mock_s3.upload_file.assert_called_once_with('/tmp/file.txt', 'my-bucket', 'key.txt')
        self.assertEqual(result['status'], 'uploaded')

    def test_s3_download_calls_boto3(self):
        from epl import cloud_backend

        self._mock_boto3()
        mock_s3 = self._mock_boto3().client.return_value
        result = cloud_backend.cloud_s3_download('b', 'k', '/tmp/out.txt')
        mock_s3.download_file.assert_called_once_with('b', 'k', '/tmp/out.txt')
        self.assertEqual(result['status'], 'downloaded')

    def test_s3_delete_calls_boto3(self):
        from epl import cloud_backend

        mock_boto3 = self._mock_boto3()
        mock_s3 = mock_boto3.client.return_value
        result = cloud_backend.cloud_s3_delete('b', 'k')
        mock_s3.delete_object.assert_called_once_with(Bucket='b', Key='k')
        self.assertEqual(result['status'], 'deleted')

    def test_s3_exists_true(self):
        from epl import cloud_backend

        mock_boto3 = self._mock_boto3()
        mock_s3 = mock_boto3.client.return_value
        mock_s3.head_object.return_value = {}
        self.assertTrue(cloud_backend.cloud_s3_exists('b', 'k'))

    def test_s3_write_text(self):
        from epl import cloud_backend

        mock_boto3 = self._mock_boto3()
        mock_s3 = mock_boto3.client.return_value
        result = cloud_backend.cloud_s3_write_text('b', 'k', 'hello')
        mock_s3.put_object.assert_called_once()
        self.assertEqual(result['status'], 'written')

    def test_s3_read_text(self):
        from epl import cloud_backend

        mock_boto3 = self._mock_boto3()
        mock_s3 = mock_boto3.client.return_value
        body_mock = MagicMock()
        body_mock.read.return_value = b'hello world'
        mock_s3.get_object.return_value = {'Body': body_mock}
        text = cloud_backend.cloud_s3_read_text('b', 'k')
        self.assertEqual(text, 'hello world')

    def test_lambda_invoke(self):
        from epl import cloud_backend

        mock_boto3 = self._mock_boto3()
        mock_lambda = mock_boto3.client.return_value
        payload_mock = MagicMock()
        payload_mock.read.return_value = b'{"result": 42}'
        mock_lambda.invoke.return_value = {
            'StatusCode': 200,
            'Payload': payload_mock,
        }
        result = cloud_backend.cloud_lambda_invoke('my-func', {'key': 'val'})
        self.assertEqual(result['status_code'], 200)
        self.assertEqual(result['payload']['result'], 42)

    def test_sqs_send(self):
        from epl import cloud_backend

        mock_boto3 = self._mock_boto3()
        mock_sqs = mock_boto3.client.return_value
        mock_sqs.send_message.return_value = {'MessageId': 'msg-123'}
        result = cloud_backend.cloud_sqs_send('https://queue.url', 'hello')
        self.assertEqual(result['message_id'], 'msg-123')

    def test_sqs_receive(self):
        from epl import cloud_backend

        mock_boto3 = self._mock_boto3()
        mock_sqs = mock_boto3.client.return_value
        mock_sqs.receive_message.return_value = {
            'Messages': [
                {'MessageId': 'm1', 'Body': 'hello', 'ReceiptHandle': 'rh1'},
            ]
        }
        result = cloud_backend.cloud_sqs_receive('https://queue.url', 1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['body'], 'hello')

    def test_sqs_delete(self):
        from epl import cloud_backend

        mock_boto3 = self._mock_boto3()
        mock_sqs = mock_boto3.client.return_value
        result = cloud_backend.cloud_sqs_delete('https://queue.url', 'rh1')
        mock_sqs.delete_message.assert_called_once()
        self.assertEqual(result['status'], 'deleted')

    def test_missing_boto3_raises_helpful_error(self):
        from epl import cloud_backend

        cloud_backend._boto3 = None
        with patch.dict('sys.modules', {'boto3': None}):
            with patch('builtins.__import__', side_effect=ImportError('No module named boto3')):
                with self.assertRaises(Exception) as ctx:
                    cloud_backend._ensure_boto3()
                self.assertIn('boto3', str(ctx.exception))


# ═══════════════════════════════════════════════════════════
#  3. Stdlib dispatch tests
# ═══════════════════════════════════════════════════════════


class TestCloudStdlibDispatch(unittest.TestCase):
    """Verify call_stdlib routes cloud_* names correctly."""

    def test_unknown_cloud_function_raises(self):
        from epl.errors import RuntimeError as EPLRuntimeError
        from epl.stdlib import call_stdlib

        with self.assertRaises(EPLRuntimeError) as ctx:
            call_stdlib('cloud_nonexistent', [], 1)
        self.assertIn('Unknown cloud function', str(ctx.exception))

    def test_cloud_s3_upload_requires_args(self):
        from epl.errors import RuntimeError as EPLRuntimeError
        from epl.stdlib import call_stdlib

        with self.assertRaises(EPLRuntimeError):
            call_stdlib('cloud_s3_upload', [], 1)
        with self.assertRaises(EPLRuntimeError):
            call_stdlib('cloud_s3_upload', ['bucket', 'key'], 1)

    def test_cloud_configure_dispatches(self):
        from epl.stdlib import call_stdlib

        result = call_stdlib('cloud_configure', ['us-east-1'], 1)
        self.assertTrue(result)


# ═══════════════════════════════════════════════════════════
#  4. pyproject.toml integration
# ═══════════════════════════════════════════════════════════


class TestCloudPyprojectIntegration(unittest.TestCase):
    def test_cloud_optional_dependency_exists(self):
        toml_path = REPO_ROOT / 'pyproject.toml'
        content = toml_path.read_text(encoding='utf-8')
        self.assertIn('cloud', content)
        self.assertIn('boto3', content)


if __name__ == '__main__':
    unittest.main()
