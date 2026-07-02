"""
EPL MCP HTTP Server — Streamable HTTP Transport
================================================
Wraps the stdio-based MCP server for cloud deployment (Azure, Smithery).
Implements MCP Streamable HTTP transport over POST /mcp.

Usage:
    gunicorn epl.mcp_http_server:app
    python -m epl.mcp_http_server  (dev mode)

Env vars:
    PORT (default: 8000)
    EPL_MCP_CORS_ORIGIN
        Allowed CORS origin for the /mcp endpoint.
        Default: "null"  — blocks all cross-origin browser requests.
        Set to your frontend origin for production deployments, e.g.:
            EPL_MCP_CORS_ORIGIN=https://your-app.example.com
        Set to "*" only for fully public, unauthenticated tool endpoints.
        NEVER use "*" when the MCP server has access to sensitive resources
        or executes code on behalf of authenticated users.
"""

from __future__ import annotations

import json
import os
import sys
import time

from flask import Flask, Response, jsonify, request

from epl.mcp_server import TOOLS, _get_version, _handle_request

app = Flask(__name__)

# ── CORS Middleware ───────────────────────────────────────────────────

# Default "null": blocks all cross-origin browser requests.
# Set EPL_MCP_CORS_ORIGIN to your frontend origin for production use.
# Never use "*" unless the endpoint is intentionally public and unauthenticated.
CORS_ORIGIN = os.environ.get('EPL_MCP_CORS_ORIGIN', 'null')


@app.after_request
def add_cors_headers(response: Response) -> Response:
    response.headers['Access-Control-Allow-Origin'] = CORS_ORIGIN
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


# ── Health Check ─────────────────────────────────────────────────────


# Written into the shipped zip by deploy-mcp.yml; absent in normal installs.
_BUILD_COMMIT_MARKER = os.path.join(os.path.dirname(__file__), '_build_commit.txt')


def _get_commit() -> str | None:
    """Return the git commit this server was deployed from, if recorded.

    The deploy workflow writes ``epl/_build_commit.txt`` into the shipped zip so
    ``/health`` can prove *which* source is actually running. A version string
    alone can't: a between-release redeploy (source fix, no version bump) that
    silently failed to apply would still report the expected version. The commit
    is unique per deploy, so the deploy pipeline can assert the live server is
    running exactly what it shipped. Absent for normal (PyPI/local) installs,
    where this returns ``None``.
    """
    try:
        with open(_BUILD_COMMIT_MARKER, encoding='utf-8') as fh:
            return fh.read().strip() or None
    except OSError:
        return None


@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify(
        {
            'status': 'ok',
            'server': 'epl-mcp-server',
            'version': _get_version(),
            'commit': _get_commit(),
            'tools': len(TOOLS),
            'transport': 'streamable-http',
        }
    )


# ── MCP Streamable HTTP Endpoint ─────────────────────────────────────


@app.route('/mcp', methods=['POST', 'OPTIONS'])
def mcp_endpoint():
    if request.method == 'OPTIONS':
        return Response('', status=204)

    content_type = request.content_type or ''
    if 'json' not in content_type:
        return jsonify({'error': 'Content-Type must be application/json'}), 415

    try:
        body = request.get_json(force=True)
    except Exception:
        return jsonify(
            {
                'jsonrpc': '2.0',
                'id': None,
                'error': {'code': -32700, 'message': 'Parse error'},
            }
        ), 400

    # Handle batch requests (array of JSON-RPC)
    if isinstance(body, list):
        responses = []
        for req in body:
            resp = _handle_request(req)
            if resp is not None:
                responses.append(resp)
        return Response(
            json.dumps(responses),
            status=200,
            content_type='application/json',
        )

    # Single JSON-RPC request
    response = _handle_request(body)

    if response is None:
        # Notification — no response needed
        return Response('', status=204)

    return Response(
        json.dumps(response),
        status=200,
        content_type='application/json',
    )


# ── SSE Endpoint (for streaming-capable clients) ─────────────────────


@app.route('/mcp/sse', methods=['GET'])
def mcp_sse():
    """Server-Sent Events endpoint for MCP streaming transport."""

    def event_stream():
        yield 'event: endpoint\ndata: /mcp\n\n'
        # Keep connection alive
        while True:
            yield ': ping\n\n'
            time.sleep(30)

    return Response(
        event_stream(),
        status=200,
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        },
    )


# ── Server Card (for Smithery auto-discovery) ────────────────────────


@app.route('/.well-known/mcp/server-card.json', methods=['GET'])
def server_card():
    return jsonify(
        {
            'name': 'epl-mcp-server',
            'description': (
                'MCP Server for EPL (English Programming Language). '
                'Validate, execute, transpile EPL code, search examples, '
                'and look up syntax references and error codes.'
            ),
            'version': _get_version(),
            'tools': [{'name': t['name'], 'description': t['description']} for t in TOOLS],
            'transport': {
                'type': 'streamable-http',
                'url': '/mcp',
            },
        }
    )


# ── Entry Point ──────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f'[epl-mcp-http] Starting on http://0.0.0.0:{port}', file=sys.stderr)
    print('[epl-mcp-http] MCP endpoint: POST /mcp', file=sys.stderr)
    print('[epl-mcp-http] Health: GET /health', file=sys.stderr)
    app.run(host='0.0.0.0', port=port, debug=False)
