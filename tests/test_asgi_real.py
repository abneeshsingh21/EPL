"""Real ASGI integration coverage using uvicorn and the EPL ASGI adapter."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import urllib.parse

import pytest


ROOT = Path(__file__).resolve().parents[1]
HAS_UVICORN = importlib.util.find_spec("uvicorn") is not None
pytestmark = pytest.mark.skipif(not HAS_UVICORN, reason="uvicorn is not installed")

ASGI_APP_CODE = """
import sys
sys.path.insert(0, {root!r})
from epl import ast_nodes as ast
from epl.web import EPLWebApp
from epl.deploy import ASGIAdapter

app = EPLWebApp("ASGITest")
app.cors_enabled = True
app.cors_origins = "*"
app.rate_limit = 0

app.add_route("/", "page", [
    ast.PageDef("Home", [
        ast.HtmlElement("heading", ast.Literal("ASGI Works")),
    ])
], method="GET")

app.add_route("/api/ping", "json", [
    ast.FetchStatement("pings")
], method="GET")

app.add_route("/api/ping", "action", [
    ast.StoreStatement("pings", field_name="msg"),
], method="POST")

application = ASGIAdapter(app)
"""


def _pick_free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait_for_server(base_url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(f"{base_url}/_health", timeout=0.5):
                return
        except Exception:
            time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for ASGI server at {base_url}")


def _stop_process(proc: subprocess.Popen[str]) -> str:
    if proc.poll() is None:
        proc.terminate()
        try:
            stdout, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, _ = proc.communicate(timeout=5)
        return stdout or ""
    stdout, _ = proc.communicate(timeout=5)
    return stdout or ""


def test_real_asgi_uvicorn_integration(tmp_path):
    module_name = "_tmp_asgi_app"
    module_path = tmp_path / f"{module_name}.py"
    module_path.write_text(ASGI_APP_CODE.format(root=str(ROOT)), encoding="utf-8")

    port = _pick_free_port()
    base = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        str(ROOT)
        if not env.get("PYTHONPATH")
        else os.pathsep.join([str(ROOT), env["PYTHONPATH"]])
    )

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            f"{module_name}:application",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(tmp_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_server(base)

        health = json.loads(urlopen(f"{base}/_health", timeout=5).read().decode("utf-8"))
        assert health["status"] == "healthy"

        resp = urlopen(f"{base}/", timeout=5)
        html = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "ASGI Works" in html
        assert "text/html" in resp.headers.get("Content-Type", "")

        resp = urlopen(f"{base}/api/ping", timeout=5)
        data = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert "application/json" in resp.headers.get("Content-Type", "")
        assert "collection" in data

        body = urllib.parse.urlencode({"msg": "hello-asgi"}).encode()
        req = Request(
            f"{base}/api/ping",
            data=body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = urlopen(req, timeout=5)
        assert resp.status == 200

        data = json.loads(urlopen(f"{base}/api/ping", timeout=5).read().decode("utf-8"))
        assert data.get("count", 0) >= 1

        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"{base}/does-not-exist", timeout=5)
        assert exc_info.value.code == 404

        options_resp = urlopen(Request(f"{base}/anything", method="OPTIONS"), timeout=5)
        assert options_resp.status == 200
        assert options_resp.headers.get("Access-Control-Allow-Origin") == "*"

        security_resp = urlopen(f"{base}/_health", timeout=5)
        security_resp.read()
        assert security_resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert security_resp.headers.get("X-Frame-Options") == "SAMEORIGIN"

        json_req = Request(
            f"{base}/api/ping",
            data=json.dumps({"msg": "json-asgi"}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        json_resp = urlopen(json_req, timeout=5)
        assert json_resp.status == 200

        query_health = json.loads(urlopen(f"{base}/_health?check=true", timeout=5).read().decode("utf-8"))
        assert query_health["status"] == "healthy"

        def fetch(_):
            response = urlopen(f"{base}/", timeout=5)
            response.read()
            return response.status

        with ThreadPoolExecutor(max_workers=10) as executor:
            statuses = list(executor.map(fetch, range(20)))
        assert statuses.count(200) == 20
    finally:
        _stop_process(proc)
