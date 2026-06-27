"""Runtime smoke test for the *subdirectory* starter examples (``examples/<name>/main.epl``).

Why this file exists
--------------------
The two existing example gates only see the top of the tree:

* ``test_examples_run.py``   globs ``examples/*.epl``        (top-level only)
* ``test_examples_parse.py`` globs ``examples/apps/*.epl``   (the apps/ folder)

Every starter that ships in its own folder — ``examples/calculator/main.epl``,
``examples/hello_web/main.epl``, ``examples/official_starters/*/main.epl`` … —
falls through *both* globs. So when an automated "AUTO-FIX" pass (v7.4.0, commit
e35d948) deleted essential lines from all seven, nothing caught it: they still
parsed, but crashed the moment they ran. The breakage shipped for releases.

A parse-only check would NOT have caught it — the corrupted files parsed
cleanly. The only thing that catches this class of bug is *executing* each
example the way it is meant to run:

* **run-to-completion** programs (no ``Start app on port``) must exit ``0``;
* **web servers** must bind their port, stay alive, and serve their body-less
  GET routes without surfacing an EPL error in the response. (EPL returns a
  failed route handler as HTTP 200 with an error *body*, so a status-code check
  is not enough — we scan the body for error signatures like ``[E0…]`` and
  "has not been created".)

Exclusions
----------
``discord_agent/main.epl`` deliberately exits non-zero until the external secret
``DISCORD_TOKEN`` is set, so it cannot run unattended. It is still covered by the
recursive parse check in ``test_examples_parse.py``.

Anything else added under ``examples/<dir>/main.epl`` is covered automatically
(fail-closed): a new run-to-completion example must exit clean, a new server must
boot and serve.
"""

from __future__ import annotations

import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _REPO_ROOT / 'examples'

# Needs an external secret (DISCORD_TOKEN); guards itself with a clean error and
# exits non-zero, so it cannot "run clean" unattended. Still parse-checked.
_NEEDS_SECRET = {'discord_agent'}

# Substrings that mean an EPL program reported an error (parser/runtime). If any
# of these show up in a served response body, the route handler is broken even
# though the HTTP status is 200.
_ERROR_SIGNATURES = (
    '[E0',                    # EPL error codes: [E0200] parser, [E0500] name, …
    'has not been created',
    'has not been defined',
    'Traceback (most recent call last)',
)

# How long to wait for a server to bind its port before declaring it dead.
_BIND_TIMEOUT_S = 25.0


def _starter_mains():
    """Every ``examples/<…>/main.epl`` except the ones needing external secrets."""
    found = sorted(_EXAMPLES_DIR.rglob('main.epl'))
    return [p for p in found if p.parent.name not in _NEEDS_SECRET]


def _is_server(src: str) -> bool:
    return 'Start app on port' in src


def _server_port(src: str) -> int:
    m = re.search(r'Start app on port\s+(\d+)', src)
    assert m, 'server example has no parseable "Start app on port <N>"'
    return int(m.group(1))


def _safe_get_routes(src: str) -> list[str]:
    """Static GET-able routes that do NOT read the request body.

    We split the source on each ``Route "…"`` header; the text up to the next
    header is that route's handler. A route is safe to probe with a plain GET if
    its path has no ``{param}`` placeholder and its handler never calls
    ``web_request_data`` (i.e. it does not expect a POST body).
    """
    routes: list[str] = []
    chunks = re.split(r'(?m)^Route\s+"', src)
    for chunk in chunks[1:]:
        m = re.match(r'([^"]+)"', chunk)
        if not m:
            continue
        path = m.group(1)
        if '{' in path:                      # parameterised route — needs a real id
            continue
        if 'web_request_data' in chunk:      # reads a request body — skip for GET
            continue
        routes.append(path)
    return routes


def _port_open(port: int) -> bool:
    s = socket.socket()
    s.settimeout(1)
    try:
        return s.connect_ex(('127.0.0.1', port)) == 0
    finally:
        s.close()


def _assert_clean_body(label: str, body: str) -> None:
    for sig in _ERROR_SIGNATURES:
        assert sig not in body, (
            f'{label} returned an EPL error in its response body '
            f'(found {sig!r}):\n{body[:600]}'
        )


# ── run-to-completion examples ──────────────────────────────────────────────

_RUN_EXAMPLES = [p for p in _starter_mains() if not _is_server(p.read_text(encoding='utf-8'))]
_SERVER_EXAMPLES = [p for p in _starter_mains() if _is_server(p.read_text(encoding='utf-8'))]


def test_starter_examples_present():
    assert _starter_mains(), 'no examples/<dir>/main.epl files found'


@pytest.mark.parametrize('example', _RUN_EXAMPLES, ids=lambda p: p.parent.name)
def test_run_to_completion_example_exits_clean(example: Path):
    result = subprocess.run(
        [sys.executable, '-m', 'epl', 'run', str(example)],
        cwd=str(_REPO_ROOT),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f'{example.parent.name}/main.epl exited {result.returncode}\n'
        f'--- stdout ---\n{result.stdout[-1500:]}\n'
        f'--- stderr ---\n{result.stderr[-1500:]}'
    )


@pytest.mark.parametrize('example', _SERVER_EXAMPLES, ids=lambda p: p.parent.name)
def test_server_example_boots_and_serves(example: Path):
    src = example.read_text(encoding='utf-8')
    port = _server_port(src)
    routes = _safe_get_routes(src)
    assert routes, f'{example.parent.name}: no body-less GET route to probe'

    proc = subprocess.Popen(
        [sys.executable, '-u', '-m', 'epl', 'run', str(example)],
        cwd=str(_REPO_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + _BIND_TIMEOUT_S
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ''
                pytest.fail(
                    f'{example.parent.name}/main.epl exited before binding port {port} '
                    f'(rc={proc.returncode})\n--- output ---\n{out[-1500:]}'
                )
            if _port_open(port):
                break
            time.sleep(0.2)
        else:
            pytest.fail(f'{example.parent.name}/main.epl never opened port {port}')

        # The server is up. Probe every safe GET route and require at least one
        # clean 200 — proving the handlers actually execute, not just that the
        # process is alive.
        served_ok = 0
        for path in routes:
            url = f'http://127.0.0.1:{port}{path}'
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    status = resp.status
                    body = resp.read().decode('utf-8', 'replace')
            except Exception as exc:  # noqa: BLE001
                pytest.fail(f'{example.parent.name}: GET {path} raised {exc}')
            _assert_clean_body(f'{example.parent.name} GET {path}', body)
            if status == 200:
                served_ok += 1
        assert served_ok, (
            f'{example.parent.name}: no probed route returned 200 '
            f'(tried {routes})'
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
