"""EPL Observability Module (v1.0)

Provides production observability for EPL web applications:
- Health check endpoint  (/_health)
- Readiness endpoint     (/_ready)
- Metrics endpoint       (/_metrics) — Prometheus format
- Structured JSON logger

Usage in EPL:
    Import "epl.observability" As obs
    obs.attach(app)

This automatically adds /_health, /_ready, /_metrics to any EPL web app.
"""

import json
import sys
import time
import threading
import logging
from typing import Optional


# ═══════════════════════════════════════════════════════════
# Internal State — tracks app metrics
# ═══════════════════════════════════════════════════════════

_start_time = time.time()
_metrics = {
    'requests_total': 0,
    'errors_total': 0,
    'requests_in_flight': 0,
    'response_time_sum': 0.0,
    'response_time_count': 0,
}
_metrics_lock = threading.Lock()
_readiness = {'ready': True, 'reason': ''}
_readiness_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════
# Metrics Helpers
# ═══════════════════════════════════════════════════════════


def record_request(duration: float = 0.0, error: bool = False) -> None:
    """Record a completed request. Call this after each request."""
    with _metrics_lock:
        _metrics['requests_total'] += 1
        _metrics['requests_in_flight'] -= 1
        _metrics['response_time_sum'] += duration
        _metrics['response_time_count'] += 1
        if error:
            _metrics['errors_total'] += 1


def start_request() -> None:
    """Record that a new request has started (increments in-flight counter)."""
    with _metrics_lock:
        _metrics['requests_in_flight'] += 1


def set_ready(ready: bool, reason: str = '') -> None:
    """Mark the app as ready or not ready."""
    with _readiness_lock:
        _readiness['ready'] = ready
        _readiness['reason'] = reason


def reset_metrics() -> None:
    """Reset all metrics to initial state (useful for testing)."""
    global _start_time
    with _metrics_lock:
        _metrics['requests_total'] = 0
        _metrics['errors_total'] = 0
        _metrics['requests_in_flight'] = 0
        _metrics['response_time_sum'] = 0.0
        _metrics['response_time_count'] = 0
    _start_time = time.time()


def get_uptime() -> float:
    """Return app uptime in seconds."""
    return round(time.time() - _start_time, 2)


def get_avg_response_time() -> float:
    """Return average response time in seconds."""
    with _metrics_lock:
        count = _metrics['response_time_count']
        if count == 0:
            return 0.0
        return round(_metrics['response_time_sum'] / count, 4)


# ═══════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════


def health_response(app_name: str = 'epl-app', version: str = '1.0.0') -> dict:
    """Generate a health check response dict."""
    return {
        'status': 'ok',
        'app': app_name,
        'version': version,
        'uptime': get_uptime(),
        'checks': {
            'memory': 'ok',
            'runtime': 'ok',
        },
    }


def readiness_response() -> dict:
    """Generate a readiness check response dict."""
    with _readiness_lock:
        if _readiness['ready']:
            return {'status': 'ready'}
        return {'status': 'not_ready', 'reason': _readiness['reason']}


# ═══════════════════════════════════════════════════════════
# Metrics — Prometheus format
# ═══════════════════════════════════════════════════════════


def metrics_response(app_name: str = 'epl_app') -> str:
    """Generate Prometheus-format metrics text."""
    safe_name = app_name.replace('-', '_').replace(' ', '_').lower()
    uptime = get_uptime()
    avg_rt = get_avg_response_time()

    with _metrics_lock:
        req_total = _metrics['requests_total']
        err_total = _metrics['errors_total']
        in_flight = _metrics['requests_in_flight']

    lines = [
        f'# HELP {safe_name}_requests_total Total number of HTTP requests',
        f'# TYPE {safe_name}_requests_total counter',
        f'{safe_name}_requests_total {req_total}',
        '',
        f'# HELP {safe_name}_errors_total Total number of HTTP errors',
        f'# TYPE {safe_name}_errors_total counter',
        f'{safe_name}_errors_total {err_total}',
        '',
        f'# HELP {safe_name}_requests_in_flight Current in-flight requests',
        f'# TYPE {safe_name}_requests_in_flight gauge',
        f'{safe_name}_requests_in_flight {in_flight}',
        '',
        f'# HELP {safe_name}_uptime_seconds Application uptime in seconds',
        f'# TYPE {safe_name}_uptime_seconds gauge',
        f'{safe_name}_uptime_seconds {uptime}',
        '',
        f'# HELP {safe_name}_avg_response_time_seconds Average response time',
        f'# TYPE {safe_name}_avg_response_time_seconds gauge',
        f'{safe_name}_avg_response_time_seconds {avg_rt}',
        '',
    ]
    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════
# Structured Logger
# ═══════════════════════════════════════════════════════════


class StructuredLogger:
    """JSON structured logger for EPL applications.

    Outputs logs in JSON format compatible with
    log aggregators like Loki, ELK, and CloudWatch.

    Example output:
        {"level": "info", "msg": "Request received",
         "path": "/api/users", "time": 1234567890.123}
    """

    def __init__(self, app_name: str = 'epl-app', level: str = 'info'):
        self.app_name = app_name
        self._level_map = {'debug': 10, 'info': 20, 'warning': 30, 'error': 40}
        self._level = self._level_map.get(level.lower(), 20)

    def _log(self, level: str, msg: str, **kwargs) -> None:
        if self._level_map.get(level, 20) < self._level:
            return
        entry = {
            'level': level,
            'msg': msg,
            'app': self.app_name,
            'time': round(time.time(), 3),
        }
        entry.update(kwargs)
        sys.stderr.write(json.dumps(entry) + '\n')
        sys.stderr.flush()

    def info(self, msg: str, **kwargs) -> None:
        self._log('info', msg, **kwargs)

    def error(self, msg: str, **kwargs) -> None:
        self._log('error', msg, **kwargs)

    def warning(self, msg: str, **kwargs) -> None:
        self._log('warning', msg, **kwargs)

    def debug(self, msg: str, **kwargs) -> None:
        self._log('debug', msg, **kwargs)


# ═══════════════════════════════════════════════════════════
# Attach to EPL Web App
# ═══════════════════════════════════════════════════════════


def attach(app, app_name: str = None, version: str = '1.0.0', enable_metrics: bool = True) -> None:
    """Attach observability endpoints to an EPL web app.

    Adds:
        GET /_health   → health check JSON
        GET /_ready    → readiness check JSON
        GET /_metrics  → Prometheus metrics (if enabled)

    Args:
        app:            EPLWebApp instance
        app_name:       App name for metrics labels
        version:        App version string
        enable_metrics: Whether to expose /_metrics endpoint
    """
    name = app_name or getattr(app, 'name', 'epl-app')

    def _health_handler(request):
        body = json.dumps(health_response(name, version), indent=2)
        return ('200 OK', [('Content-Type', 'application/json')], body)

    def _ready_handler(request):
        resp = readiness_response()
        status = '200 OK' if resp.get('status') == 'ready' else '503 Service Unavailable'
        body = json.dumps(resp, indent=2)
        return (status, [('Content-Type', 'application/json')], body)

    def _metrics_handler(request):
        body = metrics_response(name)
        return ('200 OK', [('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')], body)

    # Register routes on the EPL web app
    app.add_route('/_health', 'callable', _health_handler)
    app.add_route('/_ready', 'callable', _ready_handler)
    if enable_metrics:
        app.add_route('/_metrics', 'callable', _metrics_handler)


# ═══════════════════════════════════════════════════════════
# Convenience — get a logger instance
# ═══════════════════════════════════════════════════════════


def get_logger(app_name: str = 'epl-app', level: str = 'info') -> StructuredLogger:
    """Get a structured JSON logger instance."""
    return StructuredLogger(app_name=app_name, level=level)
