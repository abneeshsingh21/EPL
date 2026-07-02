"""
EPL MCP Server — tool-handler regression tests
==============================================
Covers the functional behavior of the MCP tools exposed by epl.mcp_server
(both the stdio server and, transitively, the HTTP wrapper which reuses the
same handlers). Focused on three fixes:

  1. epl_transpile supports the 'node' target (not just python/javascript).
  2. epl_run executes on the VM (the CLI's real engine) with a single,
     non-duplicated stream of output, and surfaces errors cleanly.
  3. epl_syntax_reference resolves intuitive topic aliases (classes->oop,
     loops->control_flow) instead of silently missing.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.mcp_server import (  # noqa: E402
    TOOLS,
    _handle_request,
    _tool_run,
    _tool_syntax_reference,
    _tool_transpile,
)

# ── epl_transpile ────────────────────────────────────────────────────────────


def test_transpile_enum_includes_node():
    tool = next(t for t in TOOLS if t['name'] == 'epl_transpile')
    enum = tool['inputSchema']['properties']['target']['enum']
    assert enum == ['python', 'javascript', 'node']


def test_transpile_python():
    r = json.loads(_tool_transpile({'code': 'Say "hi"', 'target': 'python'}))
    assert r.get('target') == 'python'
    assert 'error' not in r
    assert r['code'].strip()


def test_transpile_javascript():
    r = json.loads(_tool_transpile({'code': 'Say "hi"', 'target': 'javascript'}))
    assert r.get('target') == 'javascript'
    assert 'error' not in r
    assert r['code'].strip()


def test_transpile_node():
    r = json.loads(_tool_transpile({'code': 'Say "hi"', 'target': 'node'}))
    assert r.get('target') == 'node'
    assert 'error' not in r
    assert r['code'].strip()


def test_transpile_unknown_target_errors():
    r = json.loads(_tool_transpile({'code': 'Say "hi"', 'target': 'rust'}))
    assert 'error' in r
    assert 'node' in r['error']  # error lists the valid targets


# ── epl_run ──────────────────────────────────────────────────────────────────


def test_run_produces_output_exactly_once():
    r = json.loads(_tool_run({'code': 'Say "hello from vm"', 'timeout': 20}))
    assert r.get('exit_code') == 0
    # Exactly one occurrence — the VM streams live; a naive interpreter
    # fallback after partial VM output would duplicate this line.
    assert r['output'].count('hello from vm') == 1


def test_run_surfaces_errors():
    r = json.loads(_tool_run({'code': 'Say hello (((broken', 'timeout': 20}))
    assert r.get('exit_code') != 0
    assert r.get('error')


def test_run_surfaces_runtime_error_without_interpreter_fallback():
    # A runtime error (undefined name) must be surfaced honestly, NOT silently
    # re-run through the tree-walking interpreter. Re-execution would re-fire any
    # side effects a program performed before raising, so epl_run would report
    # behavior no real `epl run` produces. VM-only + honest error is the contract.
    r = json.loads(_tool_run({'code': 'Say undefined_name_xyz', 'timeout': 20}))
    assert r.get('exit_code') != 0
    assert r.get('error')
    assert not r.get('output')


def test_run_empty_code():
    r = json.loads(_tool_run({'code': '   ', 'timeout': 10}))
    assert r.get('error')


# ── epl_syntax_reference ─────────────────────────────────────────────────────


def test_syntax_alias_classes_resolves_to_oop():
    out = _tool_syntax_reference({'topic': 'classes'})
    assert 'No section matched' not in out
    # 'oop' and its alias 'classes' should return the same section.
    assert out == _tool_syntax_reference({'topic': 'oop'})


def test_syntax_alias_loops_resolves_to_control_flow():
    out = _tool_syntax_reference({'topic': 'loops'})
    assert 'No section matched' not in out
    assert out == _tool_syntax_reference({'topic': 'control_flow'})


def test_syntax_real_topic_still_works():
    out = _tool_syntax_reference({'topic': 'web'})
    assert 'No section matched' not in out


def test_syntax_unknown_topic_lists_available():
    out = _tool_syntax_reference({'topic': 'definitely_not_a_topic'})
    assert 'No section matched' in out
    assert 'Available topics' in out


# ── JSON-RPC dispatch (both transports share this) ───────────────────────────


def test_tools_list_dispatch():
    resp = _handle_request({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
    names = {t['name'] for t in resp['result']['tools']}
    assert {'epl_transpile', 'epl_run', 'epl_syntax_reference'} <= names


def test_tools_call_transpile_node_via_dispatch():
    resp = _handle_request(
        {
            'jsonrpc': '2.0',
            'id': 2,
            'method': 'tools/call',
            'params': {
                'name': 'epl_transpile',
                'arguments': {'code': 'Say "hi"', 'target': 'node'},
            },
        }
    )
    text = resp['result']['content'][0]['text']
    payload = json.loads(text)
    assert payload.get('target') == 'node'
    assert 'error' not in payload
