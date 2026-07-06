"""Path-traversal regression tests for web_send_file (M4).

A request-controlled path must not be able to escape the served root and
read arbitrary files (../../etc/passwd, absolute paths). Served files are
jailed to EPL_WEB_FILE_ROOT (default CWD).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.errors import RuntimeError as EPLRuntimeError
from epl.stdlib import call_stdlib


@pytest.fixture()
def jail(tmp_path, monkeypatch):
    root = tmp_path / "served"
    root.mkdir()
    (root / "ok.txt").write_text("hello")
    monkeypatch.setenv("EPL_WEB_FILE_ROOT", str(root))
    return root


def _is_jail_error(exc: Exception) -> bool:
    return "outside the allowed directory" in str(exc)


@pytest.mark.parametrize(
    "evil",
    [
        "../../../../../../etc/passwd",
        "..\\..\\..\\..\\windows\\win.ini",
        "/etc/passwd",
        "C:/Windows/System32/drivers/etc/hosts",
        "subdir/../../../../secret",
    ],
)
def test_traversal_and_absolute_paths_blocked(jail, evil):
    with pytest.raises(EPLRuntimeError) as ei:
        call_stdlib("web_send_file", [evil], 0)
    assert _is_jail_error(ei.value), f"{evil!r} should be blocked by the jail"


def test_legit_in_root_path_passes_jail(jail):
    # A valid in-root path must NOT be rejected by the jail. It still fails
    # inside flask.send_file (no active request context off-server) — that
    # failure proves it got past the jail check.
    with pytest.raises(EPLRuntimeError) as ei:
        call_stdlib("web_send_file", ["ok.txt"], 0)
    assert not _is_jail_error(ei.value), "legit in-root path was wrongly jailed"


def test_absolute_path_inside_root_allowed(jail):
    inside = str(jail / "ok.txt")
    with pytest.raises(EPLRuntimeError) as ei:
        call_stdlib("web_send_file", [inside], 0)
    assert not _is_jail_error(ei.value), "absolute path inside root was wrongly jailed"
