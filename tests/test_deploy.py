"""Tests for EPL Production Deployment Module (v4.0)

Tests WSGI adapter, ASGI adapter, Nginx/Gunicorn/Tomcat config generators,
Docker config, systemd service, and deploy CLI.
"""
import json
import os
import sys
import unittest
import asyncio
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.web import EPLWebApp, Request, Response
from epl.deploy import (
    WSGIAdapter, ASGIAdapter,
    generate_gunicorn_config, generate_wsgi_entry,
    generate_nginx_config, generate_tomcat_config,
    generate_dockerfile, generate_docker_compose, generate_requirements_txt,
    generate_systemd_service, generate_asgi_entry,
    deploy_generate, deploy_cli,
)


class TestWSGIAdapter(unittest.TestCase):
    """Test WSGI adapter for Gunicorn/uWSGI compatibility."""

    def setUp(self):
        self.app = EPLWebApp("TestWSGI")
        self.app.rate_limit = 0

    def _make_environ(self, method='GET', path='/', query='', body=b'',
                       content_type='', headers=None):
        """Create a WSGI environ dict."""
        from io import BytesIO
        environ = {
            'REQUEST_METHOD': method,
            'PATH_INFO': path,
            'QUERY_STRING': query,
            'REMOTE_ADDR': '127.0.0.1',
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '8000',
            'wsgi.input': BytesIO(body),
            'wsgi.errors': BytesIO(),
            'wsgi.url_scheme': 'http',
        }
        if body:
            environ['CONTENT_LENGTH'] = str(len(body))
        if content_type:
            environ['CONTENT_TYPE'] = content_type
        if headers:
            for k, v in headers.items():
                environ['HTTP_' + k.upper().replace('-', '_')] = v
        return environ

    def test_wsgi_callable(self):
        """WSGI adapter is callable."""
        adapter = WSGIAdapter(self.app)
        self.assertTrue(callable(adapter))

    def test_wsgi_health_check(self):
        """WSGI health check endpoint returns JSON."""
        adapter = WSGIAdapter(self.app)
        environ = self._make_environ(path='/_health')
        status_holder = {}

        def start_response(status, headers, exc_info=None):
            status_holder['status'] = status
            status_holder['headers'] = headers

        result = adapter(environ, start_response)
        self.assertIn('200', status_holder['status'])
        body = b''.join(result).decode('utf-8')
        data = json.loads(body)
        self.assertEqual(data['status'], 'healthy')
        self.assertTrue(data['wsgi'])

    def test_wsgi_404(self):
        """WSGI returns 404 for unknown routes."""
        adapter = WSGIAdapter(self.app)
        environ = self._make_environ(path='/nonexistent')
        status_holder = {}

        def start_response(status, headers, exc_info=None):
            status_holder['status'] = status

        result = adapter(environ, start_response)
        self.assertIn('404', status_holder['status'])

    def test_wsgi_cors_preflight(self):
        """WSGI handles CORS OPTIONS preflight."""
        self.app.cors_enabled = True
        self.app.cors_origins = '*'
        adapter = WSGIAdapter(self.app)
        environ = self._make_environ(method='OPTIONS', path='/')
        status_holder = {}

        def start_response(status, headers, exc_info=None):
            status_holder['status'] = status
            status_holder['headers'] = dict(headers)

        adapter(environ, start_response)
        self.assertIn('200', status_holder['status'])
        self.assertEqual(status_holder['headers'].get('Access-Control-Allow-Origin'), '*')

    def test_wsgi_rate_limit(self):
        """WSGI respects rate limiting."""
        self.app.rate_limit = 1  # 1 per minute
        adapter = WSGIAdapter(self.app)
        # Clear any existing rate-limit state for this IP
        from epl.web import _rate_tracker
        _rate_tracker.clear()

        # Use a non-health-check path (health check bypasses rate limiting)
        results = []
        for _ in range(5):
            environ = self._make_environ(path='/some-page')
            status_holder = {}
            def start_response(status, headers, exc_info=None):
                status_holder['status'] = status
            adapter(environ, start_response)
            results.append(status_holder['status'])

        # First request may 404, but subsequent should be 429
        rate_limited = [r for r in results if '429' in r]
        self.assertTrue(len(rate_limited) > 0, "Rate limiting should block some requests")

    def test_wsgi_security_headers(self):
        """WSGI responses include security headers."""
        adapter = WSGIAdapter(self.app)
        environ = self._make_environ(path='/_health')
        header_dict = {}

        def start_response(status, headers, exc_info=None):
            header_dict.update(dict(headers))

        adapter(environ, start_response)
        self.assertEqual(header_dict.get('X-Content-Type-Options'), 'nosniff')

    def test_wsgi_x_forwarded_for(self):
        """WSGI respects X-Forwarded-For header."""
        adapter = WSGIAdapter(self.app)
        environ = self._make_environ(
            path='/_health',
            headers={'X-Forwarded-For': '1.2.3.4, 10.0.0.1'}
        )
        status_holder = {}

        def start_response(status, headers, exc_info=None):
            status_holder['status'] = status

        adapter(environ, start_response)
        self.assertIn('200', status_holder['status'])

    def test_wsgi_large_body_rejected(self):
        """WSGI rejects request body larger than 10MB."""
        adapter = WSGIAdapter(self.app)
        environ = self._make_environ(
            method='POST', path='/test',
            body=b'x',
            content_type='text/plain'
        )
        # Simulate a huge Content-Length
        environ['CONTENT_LENGTH'] = str(20 * 1024 * 1024)
        status_holder = {}

        def start_response(status, headers, exc_info=None):
            status_holder['status'] = status

        adapter(environ, start_response)
        self.assertIn('413', status_holder['status'])

    def test_wsgi_json_route(self):
        """WSGI serves JSON routes correctly."""
        from epl import ast_nodes as ast
        # Add a simple JSON route using SendResponse with a literal
        send = ast.SendResponse('json', ast.Literal('hello'))
        self.app.add_route('/api/test', 'json', [send], method='GET')

        adapter = WSGIAdapter(self.app)
        environ = self._make_environ(path='/api/test')
        status_holder = {}

        def start_response(status, headers, exc_info=None):
            status_holder['status'] = status
            status_holder['headers'] = dict(headers)

        result = adapter(environ, start_response)
        self.assertIn('200', status_holder['status'])
        self.assertIn('application/json', status_holder['headers'].get('Content-Type', ''))

    def test_wsgi_static_path_traversal(self):
        """WSGI prevents path traversal on static files."""
        adapter = WSGIAdapter(self.app, static_dir='static')
        environ = self._make_environ(path='/static/../../etc/passwd')
        status_holder = {}

        def start_response(status, headers, exc_info=None):
            status_holder['status'] = status

        adapter(environ, start_response)
        self.assertIn('403', status_holder['status'])

    def test_wsgi_metrics_tracking(self):
        """WSGI tracks request metrics."""
        adapter = WSGIAdapter(self.app)
        initial = self.app._metrics['requests']

        environ = self._make_environ(path='/_health')
        def start_response(status, headers, exc_info=None): pass
        adapter(environ, start_response)

        self.assertEqual(self.app._metrics['requests'], initial + 1)


class TestASGIAdapter(unittest.TestCase):
    """Test ASGI adapter for Uvicorn/Daphne/Hypercorn compatibility."""

    def setUp(self):
        self.app = EPLWebApp("TestASGI")
        self.app.rate_limit = 0

    def test_asgi_callable(self):
        """ASGI adapter is an async callable."""
        adapter = ASGIAdapter(self.app)
        self.assertTrue(callable(adapter))

    def test_asgi_health_check(self):
        """ASGI health check returns correct JSON."""
        adapter = ASGIAdapter(self.app)

        scope = {
            'type': 'http',
            'method': 'GET',
            'path': '/_health',
            'query_string': b'',
            'headers': [],
            'client': ('127.0.0.1', 12345),
            'server': ('localhost', 8000),
        }

        received = []
        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}

        async def send(message):
            received.append(message)

        asyncio.run(adapter(scope, receive, send))

        self.assertEqual(len(received), 2)
        self.assertEqual(received[0]['type'], 'http.response.start')
        self.assertEqual(received[0]['status'], 200)
        body = received[1]['body']
        data = json.loads(body.decode('utf-8'))
        self.assertEqual(data['status'], 'healthy')

    def test_asgi_404(self):
        """ASGI returns 404 for unknown routes."""
        adapter = ASGIAdapter(self.app)

        scope = {
            'type': 'http',
            'method': 'GET',
            'path': '/unknown',
            'query_string': b'',
            'headers': [],
            'client': ('127.0.0.1', 0),
            'server': ('localhost', 8000),
        }
        received = []
        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        async def send(message):
            received.append(message)

        asyncio.run(adapter(scope, receive, send))
        self.assertEqual(received[0]['status'], 404)

    def test_asgi_lifespan(self):
        """ASGI handles lifespan events."""
        adapter = ASGIAdapter(self.app)

        scope = {'type': 'lifespan'}
        events = [
            {'type': 'lifespan.startup'},
            {'type': 'lifespan.shutdown'},
        ]
        event_idx = [0]
        received = []

        async def receive():
            idx = event_idx[0]
            event_idx[0] += 1
            return events[idx]

        async def send(message):
            received.append(message)

        asyncio.run(adapter(scope, receive, send))
        types = [m['type'] for m in received]
        self.assertIn('lifespan.startup.complete', types)
        self.assertIn('lifespan.shutdown.complete', types)

    def test_asgi_post_with_body(self):
        """ASGI handles POST with JSON body."""
        adapter = ASGIAdapter(self.app)

        body = json.dumps({"key": "value"}).encode('utf-8')
        scope = {
            'type': 'http',
            'method': 'POST',
            'path': '/api/data',
            'query_string': b'',
            'headers': [
                (b'content-type', b'application/json'),
                (b'content-length', str(len(body)).encode()),
            ],
            'client': ('127.0.0.1', 0),
            'server': ('localhost', 8000),
        }
        received = []
        async def receive():
            return {'type': 'http.request', 'body': body, 'more_body': False}
        async def send(message):
            received.append(message)

        asyncio.run(adapter(scope, receive, send))
        # Should get a response (404 since no route, but that's fine)
        self.assertTrue(len(received) >= 2)


class TestGunicornConfig(unittest.TestCase):
    """Test Gunicorn configuration generator."""

    def test_basic_config(self):
        """Generates valid Python config."""
        config = generate_gunicorn_config(app_name='TestApp', port=9000)
        self.assertIn('bind = "0.0.0.0:9000"', config)
        self.assertIn('workers =', config)
        self.assertIn('TestApp', config)

    def test_ssl_config(self):
        """SSL settings included when certs provided."""
        config = generate_gunicorn_config(
            ssl_cert='/etc/ssl/cert.pem',
            ssl_key='/etc/ssl/key.pem'
        )
        self.assertIn('certfile = "/etc/ssl/cert.pem"', config)
        self.assertIn('keyfile = "/etc/ssl/key.pem"', config)

    def test_worker_count(self):
        """Explicit worker count honored."""
        config = generate_gunicorn_config(workers=8)
        self.assertIn('workers = 8', config)

    def test_timeout_setting(self):
        """Timeout setting included."""
        config = generate_gunicorn_config(timeout=300)
        self.assertIn('timeout = 300', config)

    def test_max_requests(self):
        """Max requests setting for worker recycling."""
        config = generate_gunicorn_config(max_requests=5000)
        self.assertIn('max_requests = 5000', config)

    def test_config_has_hooks(self):
        """Config includes server hooks."""
        config = generate_gunicorn_config()
        self.assertIn('def on_starting', config)
        self.assertIn('def post_fork', config)
        self.assertIn('def when_ready', config)


class TestWSGIEntry(unittest.TestCase):
    """Test WSGI entry point generator."""

    def test_generates_wsgi(self):
        """Generates valid wsgi.py content."""
        wsgi = generate_wsgi_entry()
        self.assertIn('from epl.deploy import WSGIAdapter', wsgi)
        self.assertIn('application = WSGIAdapter', wsgi)
        self.assertIn('gunicorn', wsgi.lower())

    def test_custom_module(self):
        """Custom app module name used."""
        wsgi = generate_wsgi_entry(app_module='myapp')
        self.assertIn('myapp.epl', wsgi)


class TestNginxConfig(unittest.TestCase):
    """Test Nginx configuration generator."""

    def test_basic_config(self):
        """Generates basic Nginx config."""
        config = generate_nginx_config(server_name='example.com', upstream_port=8000)
        self.assertIn('server_name example.com', config)
        self.assertIn('server 127.0.0.1:8000', config)
        self.assertIn('proxy_pass', config)

    def test_ssl_config(self):
        """SSL config with redirect and HSTS."""
        config = generate_nginx_config(
            ssl_cert='/etc/ssl/cert.pem',
            ssl_key='/etc/ssl/key.pem'
        )
        self.assertIn('ssl_certificate /etc/ssl/cert.pem', config)
        self.assertIn('return 301 https://', config)
        self.assertIn('Strict-Transport-Security', config)

    def test_websocket_proxy(self):
        """WebSocket proxy location generated."""
        config = generate_nginx_config(enable_websocket=True)
        self.assertIn('Upgrade', config)
        self.assertIn('location /ws/', config)

    def test_gzip_enabled(self):
        """Gzip compression config included."""
        config = generate_nginx_config(enable_gzip=True)
        self.assertIn('gzip on', config)
        self.assertIn('gzip_types', config)

    def test_rate_limiting(self):
        """Rate limiting zone defined."""
        config = generate_nginx_config(rate_limit='20r/s')
        self.assertIn('limit_req_zone', config)
        self.assertIn('20r/s', config)

    def test_static_files(self):
        """Static file serving by Nginx."""
        config = generate_nginx_config(static_dir='/var/www/static')
        self.assertIn('location /static/', config)
        self.assertIn('/var/www/static', config)

    def test_security_headers(self):
        """Security headers present."""
        config = generate_nginx_config()
        self.assertIn('X-Content-Type-Options', config)
        self.assertIn('X-Frame-Options', config)
        self.assertIn('server_tokens off', config)

    def test_health_check_no_rate_limit(self):
        """Health check location bypasses rate limiting."""
        config = generate_nginx_config()
        self.assertIn('location /_health', config)

    def test_custom_upstream_name(self):
        """Custom upstream block name."""
        config = generate_nginx_config(upstream_name='my_backend')
        self.assertIn('upstream my_backend', config)
        self.assertIn('proxy_pass http://my_backend', config)


class TestTomcatConfig(unittest.TestCase):
    """Test Tomcat/Apache configuration generator."""

    def test_generates_all_configs(self):
        """Returns dict with server.xml, mod_proxy.conf, mod_proxy_ajp.conf."""
        configs = generate_tomcat_config()
        self.assertIn('server.xml', configs)
        self.assertIn('mod_proxy.conf', configs)
        self.assertIn('mod_proxy_ajp.conf', configs)

    def test_server_xml(self):
        """server.xml has HTTP and AJP connectors."""
        configs = generate_tomcat_config(http_port=9080, ajp_port=9009)
        xml = configs['server.xml']
        self.assertIn('port="9080"', xml)
        self.assertIn('port="9009"', xml)
        self.assertIn('AJP/1.3', xml)
        self.assertIn('secretRequired="true"', xml)

    def test_ssl_connector(self):
        """SSL connector generated with certs."""
        configs = generate_tomcat_config(
            ssl_cert='/etc/ssl/cert.pem',
            ssl_key='/etc/ssl/key.pem'
        )
        xml = configs['server.xml']
        self.assertIn('SSLEnabled="true"', xml)
        self.assertIn('cert.pem', xml)

    def test_mod_proxy(self):
        """mod_proxy config for HTTP proxying."""
        configs = generate_tomcat_config(server_name='mysite.com', upstream_port=9000)
        proxy = configs['mod_proxy.conf']
        self.assertIn('ServerName mysite.com', proxy)
        self.assertIn('http://127.0.0.1:9000', proxy)
        self.assertIn('ProxyPass', proxy)

    def test_ajp_proxy(self):
        """AJP proxy config."""
        configs = generate_tomcat_config(ajp_port=8009)
        ajp = configs['mod_proxy_ajp.conf']
        self.assertIn('ajp://127.0.0.1:8009', ajp)

    def test_access_log_valve(self):
        """Access log valve in server.xml."""
        configs = generate_tomcat_config()
        self.assertIn('AccessLogValve', configs['server.xml'])

    def test_remote_ip_valve(self):
        """RemoteIpValve for correct client IP behind proxy."""
        configs = generate_tomcat_config()
        self.assertIn('RemoteIpValve', configs['server.xml'])


class TestDockerConfig(unittest.TestCase):
    """Test Dockerfile and docker-compose generators."""

    def test_dockerfile(self):
        """Dockerfile generated with correct settings."""
        df = generate_dockerfile(port=9000, workers=8)
        self.assertIn('FROM python:3.11-slim', df)
        self.assertIn('EXPOSE 9000', df)
        self.assertIn('EPL_WORKERS=8', df)
        self.assertIn('gunicorn', df)
        self.assertIn('HEALTHCHECK', df)
        self.assertIn('useradd', df)  # non-root user
        self.assertIn('COPY . /app', df)
        self.assertIn('pip install --no-cache-dir -r requirements.txt', df)

    def test_requirements_txt_includes_runtime_and_python_deps(self):
        """Deploy requirements include EPL runtime, Gunicorn, and manifest Python deps."""
        manifest = {
            'python-dependencies': {
                'yaml': 'pyyaml>=6',
                'requests': '*',
            }
        }
        requirements = generate_requirements_txt(manifest=manifest, epl_requirement='epl-lang==7.0.0')
        self.assertIn('epl-lang==7.0.0', requirements)
        self.assertIn('gunicorn>=21.2', requirements)
        self.assertIn('pyyaml>=6', requirements)
        self.assertIn('requests', requirements)

    def test_docker_compose_basic(self):
        """docker-compose.yml generated."""
        dc = generate_docker_compose(app_name='myapp', port=9000)
        self.assertIn('myapp', dc)
        self.assertIn('epl-network', dc)

    def test_docker_compose_with_nginx(self):
        """docker-compose includes Nginx when enabled."""
        dc = generate_docker_compose(enable_nginx=True)
        self.assertIn('nginx', dc)
        self.assertIn('80:80', dc)

    def test_docker_compose_without_nginx(self):
        """docker-compose exposes app port when no Nginx."""
        dc = generate_docker_compose(enable_nginx=False, port=9000)
        self.assertIn('9000:9000', dc)


class TestSystemdService(unittest.TestCase):
    """Test systemd service file generator."""

    def test_service_file(self):
        """Generates valid systemd unit."""
        svc = generate_systemd_service(app_name='my-epl', port=9000)
        self.assertIn('[Unit]', svc)
        self.assertIn('[Service]', svc)
        self.assertIn('[Install]', svc)
        self.assertIn('EPL_PORT=9000', svc)
        self.assertIn('gunicorn', svc)

    def test_security_hardening(self):
        """Service includes systemd security directives."""
        svc = generate_systemd_service()
        self.assertIn('NoNewPrivileges=yes', svc)
        self.assertIn('PrivateTmp=yes', svc)
        self.assertIn('ProtectSystem=strict', svc)


class TestASGIEntry(unittest.TestCase):
    """Test ASGI entry point generator."""

    def test_generates_asgi(self):
        """Generates asgi.py with correct imports."""
        asgi = generate_asgi_entry()
        self.assertIn('from epl.deploy import ASGIAdapter', asgi)
        self.assertIn('application = ASGIAdapter', asgi)
        self.assertIn('uvicorn', asgi.lower())


class TestDeployGenerate(unittest.TestCase):
    """Test deploy_generate file output."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='epl_deploy_test_')

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_generate_gunicorn(self):
        """Deploy gunicorn generates correct files."""
        files = deploy_generate('gunicorn', output_dir=self.tmpdir)
        names = [os.path.basename(f) for f in files]
        self.assertIn('gunicorn_conf.py', names)
        self.assertIn('wsgi.py', names)
        for f in files:
            self.assertTrue(os.path.isfile(f))

    def test_generate_nginx(self):
        """Deploy nginx generates config."""
        files = deploy_generate('nginx', output_dir=self.tmpdir)
        self.assertTrue(any('nginx' in f for f in files))

    def test_generate_tomcat(self):
        """Deploy tomcat generates configs."""
        files = deploy_generate('tomcat', output_dir=self.tmpdir)
        self.assertTrue(any('tomcat' in f for f in files))
        self.assertTrue(len(files) >= 3)  # server.xml, mod_proxy, mod_proxy_ajp

    def test_generate_docker(self):
        """Deploy docker generates Dockerfile + compose."""
        files = deploy_generate('docker', output_dir=self.tmpdir)
        names = [os.path.basename(f) for f in files]
        self.assertIn('Dockerfile', names)
        self.assertIn('docker-compose.yml', names)
        self.assertIn('requirements.txt', names)

    def test_generate_systemd(self):
        """Deploy systemd generates service file."""
        files = deploy_generate('systemd', output_dir=self.tmpdir, app_name='test-app')
        self.assertTrue(any('.service' in f for f in files))

    def test_generate_all(self):
        """Deploy all generates everything."""
        files = deploy_generate('all', output_dir=self.tmpdir)
        # Should have: gunicorn_conf.py, wsgi.py, nginx conf, 3 tomcat files,
        # requirements.txt, Dockerfile, docker-compose.yml, systemd .service, asgi.py
        self.assertTrue(len(files) >= 10)
        for f in files:
            self.assertTrue(os.path.isfile(f), f"Expected {f} to exist")

    def test_generate_with_ssl(self):
        """Deploy with SSL options."""
        files = deploy_generate('all', output_dir=self.tmpdir,
                                ssl_cert='/etc/ssl/cert.pem',
                                ssl_key='/etc/ssl/key.pem')
        self.assertTrue(len(files) >= 9)
        # Check Nginx has SSL
        nginx_files = [f for f in files if 'nginx' in f]
        self.assertTrue(len(nginx_files) > 0)
        with open(nginx_files[0], 'r') as f:
            content = f.read()
        self.assertIn('ssl_certificate', content)

    def test_generate_custom_port(self):
        """Deploy respects custom port."""
        files = deploy_generate('gunicorn', output_dir=self.tmpdir, port=9500)
        with open(files[0], 'r') as f:
            content = f.read()
        self.assertIn('9500', content)


class TestDeployCLI(unittest.TestCase):
    """Test deploy CLI command."""

    def test_help_output(self):
        """deploy with no args shows help (doesn't crash)."""
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            deploy_cli([])
        output = f.getvalue()
        self.assertIn('gunicorn', output)
        self.assertIn('nginx', output)
        self.assertIn('tomcat', output)
        self.assertIn('docker', output)

    def test_invalid_target(self):
        """deploy with invalid target shows error."""
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            deploy_cli(['invalid_target'])
        output = f.getvalue()
        self.assertIn('Unknown', output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
