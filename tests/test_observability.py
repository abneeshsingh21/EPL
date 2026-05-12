"""Tests for EPL Observability Module."""
import time
import json
import pytest
from epl.observability import (
    health_response,
    readiness_response,
    metrics_response,
    record_request,
    set_ready,
    get_uptime,
    get_avg_response_time,
    get_logger,
    StructuredLogger,
)


def test_health_response_status():
    result = health_response("myapp", "1.0.0")
    assert result["status"] == "ok"
    assert result["app"] == "myapp"
    assert result["version"] == "1.0.0"


def test_health_response_has_uptime():
    result = health_response()
    assert "uptime" in result
    assert result["uptime"] >= 0


def test_health_response_has_checks():
    result = health_response()
    assert "checks" in result
    assert result["checks"]["runtime"] == "ok"


def test_readiness_response_ready():
    set_ready(True)
    result = readiness_response()
    assert result["status"] == "ready"


def test_readiness_response_not_ready():
    set_ready(False, reason="database not connected")
    result = readiness_response()
    assert result["status"] == "not_ready"
    assert result["reason"] == "database not connected"
    set_ready(True)


def test_metrics_response_format():
    result = metrics_response("myapp")
    assert "requests_total" in result
    assert "errors_total" in result
    assert "uptime_seconds" in result
    assert "# HELP" in result
    assert "# TYPE" in result


def test_metrics_response_app_name():
    result = metrics_response("my-app")
    assert "my_app_requests_total" in result


def test_record_request_increments_count():
    from epl.observability import _metrics
    before = _metrics["requests_total"]
    record_request(duration=0.1)
    assert _metrics["requests_total"] == before + 1


def test_record_request_error():
    from epl.observability import _metrics
    before = _metrics["errors_total"]
    record_request(duration=0.1, error=True)
    assert _metrics["errors_total"] == before + 1


def test_get_uptime_positive():
    uptime = get_uptime()
    assert uptime >= 0


def test_get_avg_response_time():
    record_request(duration=0.2)
    record_request(duration=0.4)
    avg = get_avg_response_time()
    assert avg > 0


def test_structured_logger_info(capsys):
    logger = StructuredLogger("testapp")
    logger.info("hello world")
    captured = capsys.readouterr()
    data = json.loads(captured.err.strip())
    assert data["level"] == "info"
    assert data["msg"] == "hello world"
    assert data["app"] == "testapp"


def test_structured_logger_error(capsys):
    logger = StructuredLogger("testapp")
    logger.error("something broke", code=500)
    captured = capsys.readouterr()
    data = json.loads(captured.err.strip())
    assert data["level"] == "error"
    assert data["code"] == 500


def test_structured_logger_extra_fields(capsys):
    logger = StructuredLogger("testapp")
    logger.info("request", path="/api/users", method="GET")
    captured = capsys.readouterr()
    data = json.loads(captured.err.strip())
    assert data["path"] == "/api/users"
    assert data["method"] == "GET"


def test_get_logger_returns_instance():
    logger = get_logger("myapp")
    assert isinstance(logger, StructuredLogger)
    assert logger.app_name == "myapp"
