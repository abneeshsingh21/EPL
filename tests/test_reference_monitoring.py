import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from epl.reference_monitor import (
    BACKEND_URL_ENV,
    FULLSTACK_URL_ENV,
    REQUIRE_CONFIGURED_ENV,
    check_backend_api,
    check_fullstack_web,
    format_monitoring_report,
    main as monitor_main,
    run_monitoring,
)


ROOT = Path(__file__).resolve().parents[1]


def _pick_server(mapping):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, content_type, body = mapping.get(self.path, (404, "text/plain", b"missing"))
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_address[1]}"


class TestReferenceMonitoring(unittest.TestCase):
    def test_backend_monitor_success(self):
        server, thread, base_url = _pick_server({
            "/_health": (200, "application/json", json.dumps({"status": "ok", "uptime_seconds": 12.5}).encode("utf-8")),
            "/api/health": (200, "application/json", json.dumps({"status": "ok", "service": "reference-backend-api"}).encode("utf-8")),
        })
        try:
            result = check_backend_api(base_url, timeout=1.0)
            self.assertTrue(result["ok"])
            self.assertEqual(result["name"], "reference-backend-api")
            self.assertTrue(all(check["ok"] for check in result["checks"]))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_fullstack_monitor_success(self):
        server, thread, base_url = _pick_server({
            "/_health": (200, "application/json", json.dumps({"status": "ok", "uptime_seconds": 10.0}).encode("utf-8")),
            "/": (200, "text/html", b"<html><body>EPL Reference Fullstack</body></html>"),
            "/api/login": (200, "application/json", json.dumps({"user": "alice", "token": "demo"}).encode("utf-8")),
            "/api/notes": (200, "application/json", json.dumps({"user": "alice", "notes": [{"id": 1, "title": "Ship EPL"}]}).encode("utf-8")),
        })
        try:
            result = check_fullstack_web(base_url, timeout=1.0)
            self.assertTrue(result["ok"])
            self.assertEqual(result["name"], "reference-fullstack-web")
            self.assertTrue(all(check["ok"] for check in result["checks"]))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_run_monitoring_reports_skip_when_unconfigured(self):
        result = run_monitoring()
        self.assertFalse(result["configured"])
        self.assertTrue(result["ok"])
        self.assertIn("skipped", result["message"].lower())

    def test_report_format_mentions_failures(self):
        result = {
            "configured": True,
            "ok": False,
            "services": [{
                "name": "reference-backend-api",
                "base_url": "https://example.test",
                "ok": False,
                "checks": [{"name": "health", "ok": False, "message": "boom", "details": {}}],
            }],
        }
        report = format_monitoring_report(result)
        self.assertIn("FAIL", report)
        self.assertIn("boom", report)

    def test_cli_wrapper_emits_json(self):
        script = ROOT / "scripts" / "monitor_reference_apps.py"
        result = subprocess.run(
            [sys.executable, str(script), "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["configured"])
        self.assertTrue(payload["ok"])

    def test_main_reads_urls_from_environment(self):
        server, thread, base_url = _pick_server({
            "/_health": (200, "application/json", json.dumps({"status": "ok", "uptime_seconds": 10.0}).encode("utf-8")),
            "/api/health": (200, "application/json", json.dumps({"status": "ok", "service": "reference-backend-api"}).encode("utf-8")),
        })
        try:
            with mock.patch.dict(os.environ, {BACKEND_URL_ENV: base_url}, clear=False):
                output = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "monitor_reference_apps.py"), "--json"],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=os.environ.copy(),
                )
            self.assertEqual(output.returncode, 0, output.stdout + output.stderr)
            payload = json.loads(output.stdout)
            self.assertTrue(payload["configured"])
            self.assertTrue(payload["ok"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_require_configured_environment_flag_fails_without_urls(self):
        with mock.patch.dict(os.environ, {REQUIRE_CONFIGURED_ENV: "1"}, clear=False):
            exit_code = monitor_main(["--json"])
        self.assertEqual(exit_code, 1)
