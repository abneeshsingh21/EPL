"""
EPL Package Registry Server v1.0
=================================
A real HTTP-based package registry that serves EPL packages.

Can run as:
- Local development server (default, port 4873)
- Production server with authentication, storage, and search

API endpoints:
    GET  /api/v1/packages             — List all packages (with search query param)
    GET  /api/v1/packages/<name>      — Get package metadata
    GET  /api/v1/packages/<name>/<ver> — Get specific version
    GET  /api/v1/download/<name>/<ver> — Download package archive
    POST /api/v1/publish              — Publish a package (multipart form)
    GET  /api/v1/search?q=<query>     — Search packages
    GET  /health                      — Health check
"""

import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
import zipfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


class RegistryStorage:
    """File-based package storage backend."""

    def __init__(self, data_dir=None):
        self.data_dir = data_dir or os.path.join(os.path.expanduser('~'), '.epl', 'registry')
        self.packages_dir = os.path.join(self.data_dir, 'packages')
        self.archives_dir = os.path.join(self.data_dir, 'archives')
        self.index_file = os.path.join(self.data_dir, 'index.json')
        self._lock = threading.Lock()
        os.makedirs(self.packages_dir, exist_ok=True)
        os.makedirs(self.archives_dir, exist_ok=True)
        self._load_index()

    def _load_index(self):
        """Load or initialize the package index."""
        if os.path.exists(self.index_file):
            with open(self.index_file, 'r', encoding='utf-8') as f:
                self._index = json.load(f)
        else:
            self._index = {'packages': {}, 'updated': time.time()}
            self._save_index()

    def _save_index(self):
        """Persist the package index atomically."""
        tmp = self.index_file + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self._index, f, indent=2)
        os.replace(tmp, self.index_file)

    def list_packages(self, query=None, page=1, per_page=50):
        """List packages, optionally filtered by search query."""
        packages = self._index.get('packages', {})
        if query:
            query_lower = query.lower()
            packages = {
                name: meta for name, meta in packages.items()
                if (query_lower in name.lower() or
                    query_lower in meta.get('description', '').lower() or
                    any(query_lower in kw.lower() for kw in meta.get('keywords', [])))
            }
        total = len(packages)
        names = sorted(packages.keys())
        start = (page - 1) * per_page
        end = start + per_page
        page_names = names[start:end]
        return {
            'packages': {name: packages[name] for name in page_names},
            'total': total,
            'page': page,
            'per_page': per_page,
        }

    def get_package(self, name):
        """Get full metadata for a package."""
        return self._index.get('packages', {}).get(name)

    def get_version(self, name, version):
        """Get metadata for a specific version."""
        pkg = self.get_package(name)
        if not pkg:
            return None
        versions = pkg.get('versions', {})
        return versions.get(version)

    def publish(self, name, version, metadata, archive_data):
        """Publish a new package version."""
        if not re.match(r'^[a-z][a-z0-9_-]*$', name):
            raise ValueError(f'Invalid package name: {name}')
        if not re.match(r'^\d+\.\d+\.\d+', version):
            raise ValueError(f'Invalid version: {version}')

        with self._lock:
            packages = self._index.setdefault('packages', {})
            pkg = packages.setdefault(name, {
                'name': name,
                'description': metadata.get('description', ''),
                'author': metadata.get('author', 'unknown'),
                'license': metadata.get('license', 'MIT'),
                'keywords': metadata.get('keywords', []),
                'versions': {},
                'created': time.time(),
            })

            # Check if version already exists
            if version in pkg.get('versions', {}):
                raise ValueError(f'{name}@{version} already exists')

            # Store archive
            archive_name = f'{name}-{version}.tar.gz'
            archive_path = os.path.join(self.archives_dir, archive_name)
            with open(archive_path, 'wb') as f:
                f.write(archive_data)

            sha256 = hashlib.sha256(archive_data).hexdigest()

            # Update index
            pkg.setdefault('versions', {})[version] = {
                'version': version,
                'archive': archive_name,
                'sha256': sha256,
                'size': len(archive_data),
                'published': time.time(),
                'dependencies': metadata.get('dependencies', {}),
            }
            pkg['latest'] = version
            pkg['description'] = metadata.get('description', pkg.get('description', ''))
            pkg['updated'] = time.time()
            self._index['updated'] = time.time()
            self._save_index()

        return {'name': name, 'version': version, 'sha256': sha256}

    def get_archive_path(self, name, version):
        """Get the file path for a package archive."""
        archive_name = f'{name}-{version}.tar.gz'
        path = os.path.join(self.archives_dir, archive_name)
        return path if os.path.exists(path) else None

    def delete_version(self, name, version):
        """Delete a specific version."""
        with self._lock:
            pkg = self._index.get('packages', {}).get(name)
            if not pkg:
                return False
            versions = pkg.get('versions', {})
            if version not in versions:
                return False

            # Remove archive
            archive = versions[version].get('archive')
            if archive:
                path = os.path.join(self.archives_dir, archive)
                if os.path.exists(path):
                    os.remove(path)

            del versions[version]
            if not versions:
                del self._index['packages'][name]
            else:
                pkg['latest'] = max(versions.keys())
            self._save_index()
        return True


class RegistryHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the package registry."""

    storage = None  # Set by server
    auth_tokens = set()  # Set of valid publish tokens

    def log_message(self, format, *args):
        """Suppress default logging, use structured logging."""
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        query = parse_qs(parsed.query)

        if path == '/health':
            self._json_response({'status': 'ok', 'service': 'epl-registry', 'version': '1.0.0'})
            return

        if path == '/api/v1/packages' or path == '':
            page = int(query.get('page', ['1'])[0])
            per_page = min(int(query.get('per_page', ['50'])[0]), 200)
            q = query.get('q', [None])[0]
            result = self.storage.list_packages(query=q, page=page, per_page=per_page)
            self._json_response(result)
            return

        if path == '/api/v1/search':
            q = query.get('q', [''])[0]
            result = self.storage.list_packages(query=q)
            self._json_response(result)
            return

        # GET /api/v1/packages/<name>
        m = re.match(r'^/api/v1/packages/([a-z][a-z0-9_-]*)$', path)
        if m:
            name = m.group(1)
            pkg = self.storage.get_package(name)
            if pkg:
                self._json_response(pkg)
            else:
                self._error_response(404, f'Package not found: {name}')
            return

        # GET /api/v1/packages/<name>/<version>
        m = re.match(r'^/api/v1/packages/([a-z][a-z0-9_-]*)/(\d+\.\d+\.\d+.*)$', path)
        if m:
            name, version = m.group(1), m.group(2)
            ver = self.storage.get_version(name, version)
            if ver:
                self._json_response(ver)
            else:
                self._error_response(404, f'{name}@{version} not found')
            return

        # GET /api/v1/download/<name>/<version>
        m = re.match(r'^/api/v1/download/([a-z][a-z0-9_-]*)/(\d+\.\d+\.\d+.*)$', path)
        if m:
            name, version = m.group(1), m.group(2)
            archive_path = self.storage.get_archive_path(name, version)
            if archive_path:
                self._file_response(archive_path)
            else:
                self._error_response(404, f'Archive not found: {name}@{version}')
            return

        self._error_response(404, 'Not found')

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        if path == '/api/v1/publish':
            self._handle_publish()
            return

        self._error_response(404, 'Not found')

    def _handle_publish(self):
        """Handle package publish (multipart or JSON + archive)."""
        # Check authorization
        auth_header = self.headers.get('Authorization', '')
        if self.auth_tokens:
            token = auth_header.replace('Bearer ', '').strip()
            if token not in self.auth_tokens:
                self._error_response(401, 'Invalid or missing authorization token')
                return

        content_type = self.headers.get('Content-Type', '')
        content_length = int(self.headers.get('Content-Length', 0))

        if content_length > 50 * 1024 * 1024:  # 50MB limit
            self._error_response(413, 'Package too large (max 50MB)')
            return

        if content_length <= 0:
            self._error_response(400, 'No content')
            return

        body = self.rfile.read(content_length)

        # Try JSON-based publish (metadata + base64 archive)
        if 'application/json' in content_type:
            try:
                data = json.loads(body.decode('utf-8'))
                name = data['name']
                version = data['version']
                import base64
                archive_data = base64.b64decode(data['archive'])
                metadata = {
                    'description': data.get('description', ''),
                    'author': data.get('author', 'unknown'),
                    'license': data.get('license', 'MIT'),
                    'keywords': data.get('keywords', []),
                    'dependencies': data.get('dependencies', {}),
                }
                result = self.storage.publish(name, version, metadata, archive_data)
                self._json_response(result, 201)
            except (KeyError, ValueError) as e:
                self._error_response(400, str(e))
            except Exception as e:
                self._error_response(500, f'Internal error: {e}')
            return

        # Try multipart publish
        if 'multipart/form-data' in content_type:
            boundary = content_type.split('boundary=')[-1].strip()
            parts = self._parse_multipart(body, boundary)
            if 'metadata' not in parts or 'archive' not in parts:
                self._error_response(400, 'Missing metadata or archive part')
                return
            try:
                metadata = json.loads(parts['metadata'])
                name = metadata['name']
                version = metadata['version']
                result = self.storage.publish(name, version, metadata, parts['archive'])
                self._json_response(result, 201)
            except (KeyError, ValueError) as e:
                self._error_response(400, str(e))
            except Exception as e:
                self._error_response(500, f'Internal error: {e}')
            return

        self._error_response(400, 'Unsupported content type')

    def _parse_multipart(self, body, boundary):
        """Simple multipart/form-data parser."""
        parts = {}
        boundary_bytes = boundary.encode('utf-8')
        segments = body.split(b'--' + boundary_bytes)
        for segment in segments:
            if not segment or segment.strip() in (b'', b'--'):
                continue
            if b'\r\n\r\n' in segment:
                header_part, content = segment.split(b'\r\n\r\n', 1)
                headers_str = header_part.decode('utf-8', errors='replace')
                # Extract name from Content-Disposition
                name_match = re.search(r'name="([^"]*)"', headers_str)
                if name_match:
                    name = name_match.group(1)
                    # Remove trailing \r\n
                    if content.endswith(b'\r\n'):
                        content = content[:-2]
                    parts[name] = content
        return parts

    def _json_response(self, data, status=200):
        body = json.dumps(data, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _error_response(self, status, message):
        self._json_response({'error': message}, status)

    def _file_response(self, filepath):
        """Send a file as response."""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/gzip')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(filepath)}"')
            self.end_headers()
            self.wfile.write(data)
        except IOError:
            self._error_response(404, 'File not found')


class ThreadedRegistryServer:
    """Threaded HTTP server for the package registry."""

    def __init__(self, port=4873, data_dir=None, auth_tokens=None):
        self.port = port
        self.storage = RegistryStorage(data_dir=data_dir)
        self.auth_tokens = set(auth_tokens) if auth_tokens else set()
        self._server = None
        self._thread = None

    def start(self, background=False):
        """Start the registry server."""
        # Seed with builtin packages from local registry.json
        self._seed_builtins()

        RegistryHandler.storage = self.storage
        RegistryHandler.auth_tokens = self.auth_tokens

        from http.server import ThreadingHTTPServer
        self._server = ThreadingHTTPServer(('0.0.0.0', self.port), RegistryHandler)

        print(f"\n  ╔══════════════════════════════════════╗")
        print(f"  ║  EPL Package Registry Server v1.0    ║")
        print(f"  ╠══════════════════════════════════════╣")
        print(f"  ║  http://localhost:{self.port:<20} ║")
        print(f"  ║  Packages: {len(self.storage._index.get('packages', {})):<25}║")
        print(f"  ║  Storage: {self.storage.data_dir:<26}║")
        print(f"  ║  Auth: {'enabled' if self.auth_tokens else 'open':<30}║")
        print(f"  ║  Press Ctrl+C to stop               ║")
        print(f"  ╚══════════════════════════════════════╝\n")

        if background:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
        else:
            try:
                self._server.serve_forever()
            except KeyboardInterrupt:
                self.stop()

    def stop(self):
        if self._server:
            self._server.shutdown()
            print("\n  Registry server stopped.")

    def _seed_builtins(self):
        """Seed the registry with built-in packages from registry.json."""
        registry_json = os.path.join(os.path.dirname(__file__), 'registry.json')
        if not os.path.exists(registry_json):
            return
        try:
            with open(registry_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for name, meta in data.get('packages', {}).items():
                existing = self.storage.get_package(name)
                if not existing:
                    self.storage._index.setdefault('packages', {})[name] = {
                        'name': name,
                        'description': meta.get('description', ''),
                        'author': meta.get('author', 'EPL Team'),
                        'license': meta.get('license', 'MIT'),
                        'keywords': meta.get('keywords', []),
                        'latest': meta.get('version', '1.0.0'),
                        'type': 'builtin',
                        'versions': {
                            meta.get('version', '1.0.0'): {
                                'version': meta.get('version', '1.0.0'),
                                'type': 'builtin',
                                'published': time.time(),
                                'dependencies': {},
                            }
                        },
                        'created': time.time(),
                    }
            self.storage._save_index()
        except (json.JSONDecodeError, IOError):
            pass


class RegistryClient:
    """HTTP client for interacting with the EPL package registry."""

    def __init__(self, registry_url='http://localhost:4873'):
        self.registry_url = registry_url.rstrip('/')

    def search(self, query):
        """Search for packages."""
        import urllib.request
        url = f'{self.registry_url}/api/v1/search?q={query}'
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            return {'error': str(e)}

    def get_package(self, name):
        """Get package metadata."""
        import urllib.request
        url = f'{self.registry_url}/api/v1/packages/{name}'
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            return None

    def download(self, name, version, dest_dir):
        """Download a package archive."""
        import urllib.request
        url = f'{self.registry_url}/api/v1/download/{name}/{version}'
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=60) as resp:
                archive_path = os.path.join(dest_dir, f'{name}-{version}.tar.gz')
                with open(archive_path, 'wb') as f:
                    f.write(resp.read())
                return archive_path
        except Exception as e:
            return None

    def publish(self, name, version, metadata, archive_path, token=None):
        """Publish a package to the registry."""
        import urllib.request
        import base64

        with open(archive_path, 'rb') as f:
            archive_data = base64.b64encode(f.read()).decode('ascii')

        payload = {
            'name': name,
            'version': version,
            'archive': archive_data,
            **metadata,
        }

        body = json.dumps(payload).encode('utf-8')
        url = f'{self.registry_url}/api/v1/publish'
        req = urllib.request.Request(url, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
        if token:
            req.add_header('Authorization', f'Bearer {token}')

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            return {'error': e.read().decode('utf-8')}
        except Exception as e:
            return {'error': str(e)}


def start_registry(port=4873, data_dir=None, auth_tokens=None, background=False):
    """Start the EPL package registry server.
    
    Args:
        port: Port to listen on (default 4873)
        data_dir: Directory for package storage (default ~/.epl/registry)
        auth_tokens: List of valid auth tokens for publishing (None = open)
        background: If True, run in a background thread
    
    Returns:
        ThreadedRegistryServer instance
    """
    server = ThreadedRegistryServer(port=port, data_dir=data_dir, auth_tokens=auth_tokens)
    server.start(background=background)
    return server
