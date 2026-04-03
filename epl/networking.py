"""
EPL Networking Module v1.0
==========================
Real TCP/UDP socket programming and HTTP client.

Provides:
- TCP server and client with connection handling
- UDP server and client
- HTTP client (GET, POST, PUT, DELETE, PATCH) with headers, auth, timeouts
- SSL/TLS support
- DNS resolution
- WebSocket client
"""

import socket
import ssl
import json
import threading
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Optional
from io import BytesIO


# ─── TCP Server ───────────────────────────────────────────────

class TCPServer:
    """
    Multi-threaded TCP server.

    Usage from EPL:
        Set server To TCPServer("0.0.0.0", 8080)
        server.on_connect(Given client Do
            Set data To client.receive()
            client.send("Echo: " + data)
            client.close()
        EndGiven)
        server.start()
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080,
                 backlog: int = 128, use_ssl: bool = False,
                 certfile: str = None, keyfile: str = None):
        self.host = host
        self.port = port
        self.backlog = backlog
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._running = False
        self._handler = None
        self._clients: list = []
        self._lock = threading.Lock()

        if use_ssl and certfile:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile, keyfile)
            self._socket = ctx.wrap_socket(self._socket, server_side=True)

    def on_connect(self, handler):
        """Set the connection handler function."""
        self._handler = handler

    def start(self, blocking: bool = True):
        """Start the TCP server."""
        self._socket.bind((self.host, self.port))
        self._socket.listen(self.backlog)
        self._running = True
        print(f"TCP Server listening on {self.host}:{self.port}")

        if blocking:
            self._accept_loop()
        else:
            t = threading.Thread(target=self._accept_loop, daemon=True)
            t.start()
            return t

    def _accept_loop(self):
        self._socket.settimeout(1.0)
        while self._running:
            try:
                client_sock, addr = self._socket.accept()
                client = TCPConnection(client_sock, addr)
                with self._lock:
                    self._clients.append(client)
                if self._handler:
                    t = threading.Thread(
                        target=self._handle_client, args=(client,), daemon=True
                    )
                    t.start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_client(self, client):
        try:
            if self._handler:
                self._handler(client)
        except Exception as e:
            print(f"TCP client error: {e}")
        finally:
            client.close()
            with self._lock:
                if client in self._clients:
                    self._clients.remove(client)

    def stop(self):
        """Stop the server."""
        self._running = False
        with self._lock:
            for c in self._clients:
                c.close()
            self._clients.clear()
        self._socket.close()

    @property
    def client_count(self):
        with self._lock:
            return len(self._clients)


class TCPConnection:
    """Represents a TCP connection (client or server-side)."""

    def __init__(self, sock: socket.socket = None, addr: tuple = None):
        self._socket = sock
        self.address = addr
        self.connected = sock is not None
        self._buffer_size = 65536

    def connect(self, host: str, port: int, timeout: float = 30.0,
                use_ssl: bool = False):
        """Connect to a TCP server."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(timeout)
        if use_ssl:
            ctx = ssl.create_default_context()
            self._socket = ctx.wrap_socket(self._socket, server_hostname=host)
        self._socket.connect((host, port))
        self.address = (host, port)
        self.connected = True

    def send(self, data) -> int:
        """Send data (str or bytes)."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        return self._socket.sendall(data) or len(data)

    def send_line(self, text: str):
        """Send a line of text (with newline)."""
        return self.send(text + '\n')

    def receive(self, size: int = None) -> str:
        """Receive data as string."""
        data = self._socket.recv(size or self._buffer_size)
        return data.decode('utf-8', errors='replace')

    def receive_bytes(self, size: int = None) -> bytes:
        """Receive raw bytes."""
        return self._socket.recv(size or self._buffer_size)

    def receive_line(self) -> str:
        """Receive until newline."""
        data = b''
        while True:
            chunk = self._socket.recv(1)
            if not chunk or chunk == b'\n':
                break
            data += chunk
        return data.decode('utf-8', errors='replace').rstrip('\r')

    def receive_all(self, timeout: float = 1.0) -> str:
        """Receive all available data."""
        self._socket.settimeout(timeout)
        chunks = []
        try:
            while True:
                chunk = self._socket.recv(self._buffer_size)
                if not chunk:
                    break
                chunks.append(chunk)
        except socket.timeout:
            pass
        return b''.join(chunks).decode('utf-8', errors='replace')

    def receive_exact(self, size: int) -> bytes:
        """Receive exactly n bytes."""
        data = b''
        while len(data) < size:
            chunk = self._socket.recv(size - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        return data

    def set_timeout(self, seconds: float):
        self._socket.settimeout(seconds)

    def close(self):
        """Close the connection."""
        if self._socket and self.connected:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._socket.close()
            self.connected = False

    @property
    def local_address(self):
        return self._socket.getsockname() if self._socket else None

    @property
    def remote_address(self):
        return self.address

    def __repr__(self):
        return f"<TCPConnection to={self.address} connected={self.connected}>"


# ─── UDP ──────────────────────────────────────────────────────

class UDPSocket:
    """
    UDP socket for connectionless communication.

    Usage from EPL:
        Set udp To UDPSocket()
        udp.bind("0.0.0.0", 9999)
        Set data, addr To udp.receive_from()
        udp.send_to("reply", addr[0], addr[1])
    """

    def __init__(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._buffer_size = 65536

    def bind(self, host: str = "0.0.0.0", port: int = 0):
        """Bind to address. Port 0 = auto-assign."""
        self._socket.bind((host, port))

    def send_to(self, data, host: str, port: int):
        """Send data to address."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        self._socket.sendto(data, (host, port))

    def receive_from(self, size: int = None) -> tuple:
        """Receive data and sender address. Returns (data_str, (host, port))."""
        data, addr = self._socket.recvfrom(size or self._buffer_size)
        return data.decode('utf-8', errors='replace'), addr

    def receive_from_bytes(self, size: int = None) -> tuple:
        """Receive raw bytes and sender address."""
        return self._socket.recvfrom(size or self._buffer_size)

    def set_broadcast(self, enabled: bool = True):
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, int(enabled))

    def set_timeout(self, seconds: float):
        self._socket.settimeout(seconds)

    @property
    def local_address(self):
        return self._socket.getsockname()

    def close(self):
        self._socket.close()


# ─── HTTP Client ──────────────────────────────────────────────

class HTTPResponse:
    """Represents an HTTP response."""

    def __init__(self, status: int, headers: dict, body: bytes, url: str):
        self.status = status
        self.status_code = status
        self.headers = headers
        self.body = body
        self.url = url
        self._text = None
        self._json = None

    @property
    def text(self) -> str:
        if self._text is None:
            encoding = self.headers.get('charset', 'utf-8')
            self._text = self.body.decode(encoding, errors='replace')
        return self._text

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400

    def json(self):
        if self._json is None:
            self._json = json.loads(self.text)
        return self._json

    def __repr__(self):
        return f"<HTTPResponse status={self.status} url='{self.url}'>"

    def __bool__(self):
        return self.ok


class HTTPClient:
    """
    Full-featured HTTP client.

    Usage from EPL:
        Set http To HTTPClient()
        http.set_header("Authorization", "Bearer token123")
        Set resp To http.get("https://api.example.com/users")
        Print resp.status
        Print resp.json()
    """

    def __init__(self, base_url: str = "", timeout: float = 30.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._headers: dict = {
            'User-Agent': 'EPL-HTTPClient/1.0',
            'Accept': 'application/json, text/html, */*',
        }
        self._cookies: dict = {}
        self._auth: tuple = None
        self._verify_ssl = True

    def set_header(self, key: str, value: str):
        self._headers[key] = value
        return self

    def set_headers(self, headers: dict):
        self._headers.update(headers)
        return self

    def set_auth(self, username: str, password: str):
        """Set basic authentication."""
        import base64
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._headers['Authorization'] = f"Basic {credentials}"
        self._auth = (username, password)
        return self

    def set_bearer_token(self, token: str):
        """Set bearer token authentication."""
        self._headers['Authorization'] = f"Bearer {token}"
        return self

    def set_cookie(self, name: str, value: str):
        self._cookies[name] = value
        return self

    def set_timeout(self, seconds: float):
        self.timeout = seconds
        return self

    def set_verify_ssl(self, verify: bool):
        self._verify_ssl = verify
        return self

    def _build_url(self, path: str) -> str:
        if path.startswith(('http://', 'https://')):
            return path
        return f"{self.base_url}/{path.lstrip('/')}" if self.base_url else path

    def _make_request(self, method: str, url: str, data=None,
                      headers: dict = None, params: dict = None) -> HTTPResponse:
        """Make an HTTP request."""
        full_url = self._build_url(url)

        # Add query params
        if params:
            query = urllib.parse.urlencode(params)
            separator = '&' if '?' in full_url else '?'
            full_url += separator + query

        # Prepare headers
        req_headers = dict(self._headers)
        if headers:
            req_headers.update(headers)

        # Add cookies
        if self._cookies:
            cookie_str = '; '.join(f"{k}={v}" for k, v in self._cookies.items())
            req_headers['Cookie'] = cookie_str

        # Prepare body
        body = None
        if data is not None:
            if isinstance(data, dict):
                body = json.dumps(data).encode('utf-8')
                req_headers.setdefault('Content-Type', 'application/json')
            elif isinstance(data, str):
                body = data.encode('utf-8')
            elif isinstance(data, bytes):
                body = data
            req_headers['Content-Length'] = str(len(body))

        # Build request
        req = urllib.request.Request(
            full_url,
            data=body,
            headers=req_headers,
            method=method.upper()
        )

        # SSL context
        ctx = None
        if not self._verify_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        try:
            response = urllib.request.urlopen(req, timeout=self.timeout, context=ctx)
            resp_headers = dict(response.getheaders())
            resp_body = response.read()

            # Parse Set-Cookie headers
            for key, value in response.getheaders():
                if key.lower() == 'set-cookie':
                    parts = value.split(';')[0].split('=', 1)
                    if len(parts) == 2:
                        self._cookies[parts[0].strip()] = parts[1].strip()

            return HTTPResponse(response.status, resp_headers, resp_body, full_url)

        except urllib.error.HTTPError as e:
            resp_body = e.read() if hasattr(e, 'read') else b''
            resp_headers = dict(e.headers.items()) if hasattr(e, 'headers') else {}
            return HTTPResponse(e.code, resp_headers, resp_body, full_url)

        except urllib.error.URLError as e:
            raise ConnectionError(f"HTTP request failed: {e.reason}")

    def get(self, url: str, params: dict = None, headers: dict = None) -> HTTPResponse:
        return self._make_request('GET', url, params=params, headers=headers)

    def post(self, url: str, data=None, headers: dict = None) -> HTTPResponse:
        return self._make_request('POST', url, data=data, headers=headers)

    def put(self, url: str, data=None, headers: dict = None) -> HTTPResponse:
        return self._make_request('PUT', url, data=data, headers=headers)

    def patch(self, url: str, data=None, headers: dict = None) -> HTTPResponse:
        return self._make_request('PATCH', url, data=data, headers=headers)

    def delete(self, url: str, headers: dict = None) -> HTTPResponse:
        return self._make_request('DELETE', url, headers=headers)

    def head(self, url: str, headers: dict = None) -> HTTPResponse:
        return self._make_request('HEAD', url, headers=headers)

    def options(self, url: str, headers: dict = None) -> HTTPResponse:
        return self._make_request('OPTIONS', url, headers=headers)

    def download(self, url: str, filepath: str, chunk_size: int = 8192) -> int:
        """Download a file. Returns bytes written."""
        full_url = self._build_url(url)
        req = urllib.request.Request(full_url, headers=self._headers)

        ctx = None
        if not self._verify_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        response = urllib.request.urlopen(req, timeout=self.timeout, context=ctx)
        total = 0
        with open(filepath, 'wb') as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
        return total

    def upload(self, url: str, filepath: str, field_name: str = "file") -> HTTPResponse:
        """Upload a file using multipart/form-data."""
        import os
        filename = os.path.basename(filepath)
        boundary = f"----EPLBoundary{int(time.time()*1000)}"

        with open(filepath, 'rb') as f:
            file_data = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode('utf-8') + file_data + f"\r\n--{boundary}--\r\n".encode('utf-8')

        headers = {'Content-Type': f'multipart/form-data; boundary={boundary}'}
        return self._make_request('POST', url, data=body, headers=headers)

    def __repr__(self):
        return f"<HTTPClient base_url='{self.base_url}'>"


# ─── DNS ──────────────────────────────────────────────────────

def dns_lookup(hostname: str) -> str:
    """Resolve hostname to IP address."""
    return socket.gethostbyname(hostname)


def dns_lookup_all(hostname: str) -> list:
    """Resolve hostname to all IP addresses."""
    results = socket.getaddrinfo(hostname, None)
    ips = list(set(r[4][0] for r in results))
    return ips


def reverse_dns(ip: str) -> str:
    """Reverse DNS lookup."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except socket.herror:
        return ip


def is_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a TCP port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except (socket.error, OSError):
        return False


def get_local_ip() -> str:
    """Get local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_hostname() -> str:
    """Get the current hostname."""
    return socket.gethostname()


# ─── Convenience Functions ────────────────────────────────────

def http_get(url: str, headers: dict = None, timeout: float = 30.0) -> HTTPResponse:
    """Quick HTTP GET request."""
    client = HTTPClient(timeout=timeout)
    if headers:
        client.set_headers(headers)
    return client.get(url)


def http_post(url: str, data=None, headers: dict = None, timeout: float = 30.0) -> HTTPResponse:
    """Quick HTTP POST request."""
    client = HTTPClient(timeout=timeout)
    if headers:
        client.set_headers(headers)
    return client.post(url, data=data)


def http_put(url: str, data=None, headers: dict = None, timeout: float = 30.0) -> HTTPResponse:
    """Quick HTTP PUT request."""
    client = HTTPClient(timeout=timeout)
    if headers:
        client.set_headers(headers)
    return client.put(url, data=data)


def http_delete(url: str, headers: dict = None, timeout: float = 30.0) -> HTTPResponse:
    """Quick HTTP DELETE request."""
    client = HTTPClient(timeout=timeout)
    if headers:
        client.set_headers(headers)
    return client.delete(url)


def tcp_connect(host: str, port: int, timeout: float = 30.0,
                use_ssl: bool = False) -> TCPConnection:
    """Quick TCP connection."""
    conn = TCPConnection()
    conn.connect(host, port, timeout, use_ssl)
    return conn


def udp_socket() -> UDPSocket:
    """Create a new UDP socket."""
    return UDPSocket()
