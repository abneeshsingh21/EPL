"""Real HTTP integration test for the EPL To-Do example web app."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
import urllib.parse


ROOT = Path(__file__).resolve().parents[1]
TODO_APP = ROOT / "examples" / "todo.epl"


def _pick_free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _wait_for_server(base_url: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(f"{base_url}/_health", timeout=0.5):
                return
        except Exception:
            time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for To-Do app at {base_url}")


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


def test_todo_webapp_flow_over_http():
    port = _pick_free_port()
    base = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        str(ROOT)
        if not env.get("PYTHONPATH")
        else os.pathsep.join([str(ROOT), env["PYTHONPATH"]])
    )

    source = TODO_APP.read_text(encoding="utf-8")
    port_specific_source = source.replace("Start todoApp on port 3000", f"Start todoApp on port {port}")
    if port_specific_source == source:
        raise AssertionError("Failed to rewrite To-Do app port for integration test.")

    temp_app = ROOT / "tests" / "_tmp_todo_app.epl"
    temp_app.write_text(port_specific_source, encoding="utf-8")

    try:
        proc = subprocess.Popen(
            [sys.executable, "main.py", str(temp_app)],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _wait_for_server(base)

        resp = urlopen(f"{base}/", timeout=5)
        html = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "EPL To-Do" in html
        assert "0 task(s)" in html

        body = urllib.parse.urlencode({"task": "Buy groceries"}).encode()
        resp = urlopen(Request(f"{base}/", data=body, method="POST"), timeout=5)
        html = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "Buy groceries" in html
        assert "1 task(s)" in html

        body = urllib.parse.urlencode({"task": "Walk the dog"}).encode()
        resp = urlopen(Request(f"{base}/", data=body, method="POST"), timeout=5)
        html = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "Buy groceries" in html
        assert "Walk the dog" in html
        assert "2 task(s)" in html

        resp = urlopen(Request(f"{base}/delete", data=b"index=0", method="POST"), timeout=5)
        html = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "Buy groceries" not in html
        assert "Walk the dog" in html

        resp = urlopen(f"{base}/about", timeout=5)
        about_html = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "About EPL To-Do" in about_html

        resp = urlopen(f"{base}/api/tasks", timeout=5)
        data = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert data.get("collection") == "tasks"
        assert data.get("count", 0) >= 1
    finally:
        if "proc" in locals():
            _stop_process(proc)
        if temp_app.exists():
            temp_app.unlink()
