"""Operational monitoring helpers for deployed EPL reference apps."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

BACKEND_URL_ENV = "EPL_REFERENCE_BACKEND_URL"
FULLSTACK_URL_ENV = "EPL_REFERENCE_FULLSTACK_URL"
REQUIRE_CONFIGURED_ENV = "EPL_REFERENCE_MONITOR_REQUIRE_CONFIGURED"


def _normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def _timed_get_json(url: str, timeout: float) -> Dict[str, Any]:
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    payload = json.loads(body)
    return {"payload": payload, "elapsed_ms": elapsed_ms}


def _timed_get_text(url: str, timeout: float) -> Dict[str, Any]:
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    return {"payload": body, "elapsed_ms": elapsed_ms}


def _ok_check(name: str, details: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": name, "ok": True, "details": details}


def _failed_check(name: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"name": name, "ok": False, "message": message, "details": details or {}}


def check_backend_api(base_url: str, timeout: float = 5.0) -> Dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    checks: List[Dict[str, Any]] = []

    try:
        health = _timed_get_json(f"{base_url}/_health", timeout)
        payload = health["payload"]
        if payload.get("status") != "ok":
            checks.append(_failed_check("health", "Expected status=ok.", {"payload": payload}))
        else:
            checks.append(_ok_check("health", {"elapsed_ms": health["elapsed_ms"], "payload": payload}))
    except Exception as exc:
        checks.append(_failed_check("health", str(exc)))

    try:
        api_health = _timed_get_json(f"{base_url}/api/health", timeout)
        payload = api_health["payload"]
        if payload.get("service") != "reference-backend-api":
            checks.append(_failed_check("api-health", "Expected reference-backend-api service marker.", {"payload": payload}))
        else:
            checks.append(_ok_check("api-health", {"elapsed_ms": api_health["elapsed_ms"], "payload": payload}))
    except Exception as exc:
        checks.append(_failed_check("api-health", str(exc)))

    ok = all(check["ok"] for check in checks)
    return {"name": "reference-backend-api", "base_url": base_url, "ok": ok, "checks": checks}


def check_fullstack_web(base_url: str, timeout: float = 5.0) -> Dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    checks: List[Dict[str, Any]] = []

    try:
        health = _timed_get_json(f"{base_url}/_health", timeout)
        payload = health["payload"]
        if payload.get("status") != "ok":
            checks.append(_failed_check("health", "Expected status=ok.", {"payload": payload}))
        else:
            checks.append(_ok_check("health", {"elapsed_ms": health["elapsed_ms"], "payload": payload}))
    except Exception as exc:
        checks.append(_failed_check("health", str(exc)))

    try:
        home = _timed_get_text(f"{base_url}/", timeout)
        body = home["payload"]
        if "EPL Reference Fullstack" not in body:
            checks.append(_failed_check("home", "Landing page marker missing."))
        else:
            checks.append(_ok_check("home", {"elapsed_ms": home["elapsed_ms"]}))
    except Exception as exc:
        checks.append(_failed_check("home", str(exc)))

    try:
        login = _timed_get_json(f"{base_url}/api/login", timeout)
        payload = login["payload"]
        if payload.get("user") != "alice":
            checks.append(_failed_check("login", "Expected demo user alice.", {"payload": payload}))
        else:
            checks.append(_ok_check("login", {"elapsed_ms": login["elapsed_ms"], "payload": payload}))
    except Exception as exc:
        checks.append(_failed_check("login", str(exc)))

    try:
        notes = _timed_get_json(f"{base_url}/api/notes", timeout)
        payload = notes["payload"]
        if payload.get("user") != "alice" or not payload.get("notes"):
            checks.append(_failed_check("notes", "Expected alice notes payload.", {"payload": payload}))
        else:
            checks.append(_ok_check("notes", {"elapsed_ms": notes["elapsed_ms"], "count": len(payload.get("notes", []))}))
    except Exception as exc:
        checks.append(_failed_check("notes", str(exc)))

    ok = all(check["ok"] for check in checks)
    return {"name": "reference-fullstack-web", "base_url": base_url, "ok": ok, "checks": checks}


def run_monitoring(
    *,
    backend_url: Optional[str] = None,
    fullstack_url: Optional[str] = None,
    timeout: float = 5.0,
    require_configured: bool = False,
) -> Dict[str, Any]:
    services: List[Dict[str, Any]] = []

    if backend_url:
        services.append(check_backend_api(backend_url, timeout=timeout))
    if fullstack_url:
        services.append(check_fullstack_web(fullstack_url, timeout=timeout))

    configured = bool(services)
    if not configured and require_configured:
        return {
            "configured": False,
            "ok": False,
            "services": [],
            "message": "No reference app URLs configured.",
        }

    overall_ok = configured and all(service["ok"] for service in services)
    if not configured:
        return {
            "configured": False,
            "ok": True,
            "services": [],
            "message": "No reference app URLs configured. Monitoring skipped.",
        }

    return {
        "configured": True,
        "ok": overall_ok,
        "services": services,
    }


def format_monitoring_report(result: Dict[str, Any]) -> str:
    if not result.get("configured"):
        return result.get("message", "No monitoring targets configured.")

    lines = ["Reference app monitoring summary:"]
    for service in result.get("services", []):
        status = "PASS" if service["ok"] else "FAIL"
        lines.append(f"- {service['name']}: {status} ({service['base_url']})")
        for check in service.get("checks", []):
            check_status = "ok" if check["ok"] else "failed"
            details = check.get("details", {})
            elapsed = details.get("elapsed_ms")
            elapsed_text = f", {elapsed}ms" if elapsed is not None else ""
            suffix = f": {check.get('message')}" if not check["ok"] else ""
            lines.append(f"  - {check['name']}: {check_status}{elapsed_text}{suffix}")
    return "\n".join(lines)


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _write_github_step_summary(result: Dict[str, Any]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("## EPL Reference App Monitoring\n\n")
        handle.write("```\n")
        handle.write(format_monitoring_report(result))
        handle.write("\n```\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor deployed EPL reference apps.")
    parser.add_argument("--backend-url", help="Base URL of the deployed reference backend API.")
    parser.add_argument("--fullstack-url", help="Base URL of the deployed reference fullstack web app.")
    parser.add_argument("--timeout", type=float, default=5.0, help="Per-request timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a text summary.")
    parser.add_argument(
        "--require-configured",
        action="store_true",
        help="Fail if neither backend nor fullstack URL is configured.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    backend_url = args.backend_url or os.environ.get(BACKEND_URL_ENV)
    fullstack_url = args.fullstack_url or os.environ.get(FULLSTACK_URL_ENV)
    require_configured = args.require_configured or _env_flag(REQUIRE_CONFIGURED_ENV)
    result = run_monitoring(
        backend_url=backend_url,
        fullstack_url=fullstack_url,
        timeout=args.timeout,
        require_configured=require_configured,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(format_monitoring_report(result))
    _write_github_step_summary(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
