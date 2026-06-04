"""
EPL MCP Server — Model Context Protocol for AI Integration
===========================================================
Gives any MCP-compatible AI tool (Claude, Cursor, VS Code Copilot, Windsurf)
real-time access to EPL's parser, interpreter, transpiler, and documentation.

Usage:
    python -m epl.mcp_server

Configure in AI tool:
    {
        "mcpServers": {
            "epl": {
                "command": "python",
                "args": ["-m", "epl.mcp_server"]
            }
        }
    }

Protocol: JSON-RPC 2.0 over stdio (stdin/stdout)
Dependencies: Python stdlib only — zero external packages
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback
from typing import Any

# ── Logging (stderr only — stdout is reserved for JSON-RPC) ──────────

def _log(msg: str) -> None:
    print(f"[epl-mcp] {msg}", file=sys.stderr, flush=True)


# ── Tool Definitions ─────────────────────────────────────────────────

TOOLS = [
    {
        "name": "epl_syntax_reference",
        "description": (
            "Get EPL (English Programming Language) syntax reference with examples. "
            "Optionally filter by topic: 'variables', 'functions', 'web', 'loops', "
            "'classes', 'error_handling', 'collections', 'imports', 'gui', 'async', "
            "'enums_ternary', 'file_io', 'deploy', 'observability', '3d_canvas', "
            "'style_layout', 'js_bridge', 'misc'. "
            "CRITICAL: EPL uses 'Otherwise' not 'Else', 'Note:' not '//', "
            "and every block ends with 'End'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": (
                        "Optional topic filter. Leave empty for full reference. "
                        "Examples: 'web', 'functions', 'control_flow', 'collections'"
                    ),
                },
            },
        },
    },
    {
        "name": "epl_validate",
        "description": (
            "Validate EPL code using the real lexer, parser, and type checker. "
            "Returns syntax status, diagnostics with line numbers, and statement count. "
            "Use this to verify generated EPL code is syntactically correct."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "EPL source code to validate.",
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "epl_run",
        "description": (
            "Execute EPL code in a sandboxed subprocess with timeout. "
            "Returns program output (stdout) and any errors (stderr). "
            "Safe: runs in an isolated process with a 10-second default timeout."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "EPL source code to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 10, max: 30).",
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "epl_transpile",
        "description": (
            "Transpile EPL code to Python or JavaScript. "
            "Returns the transpiled source code in the target language."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "EPL source code to transpile.",
                },
                "target": {
                    "type": "string",
                    "enum": ["python", "javascript"],
                    "description": "Target language: 'python' or 'javascript'.",
                },
            },
            "required": ["code", "target"],
        },
    },
    {
        "name": "epl_examples",
        "description": (
            "Search EPL example files by keyword. Returns matching example filenames "
            "and their source code. Use to find real, working EPL code patterns."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search keyword. Examples: 'web', 'calculator', 'database', "
                        "'todo', 'class', 'loop', 'function', 'error', 'file'"
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "epl_error_lookup",
        "description": (
            "Look up an EPL error code or error type and get its explanation. "
            "Accepts codes like 'E0200' or names like 'ParserError'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "error_code": {
                    "type": "string",
                    "description": "Error code (e.g. 'E0200') or name (e.g. 'ParserError').",
                },
            },
            "required": ["error_code"],
        },
    },
]


# ── Tool Implementations ─────────────────────────────────────────────

def _tool_syntax_reference(args: dict) -> str:
    try:
        from epl.syntax_reference import get_syntax_sections, get_syntax_text
    except ImportError:
        return "Error: EPL is not installed. Run: pip install eplang"

    topic = args.get("topic", "").strip().lower()

    if not topic:
        return get_syntax_text()

    sections = get_syntax_sections()
    matched = []
    for section in sections:
        sid = section.get("id", "").lower()
        stitle = section.get("title", "").lower()
        if topic in sid or topic in stitle:
            matched.append(section)

    if not matched:
        all_ids = [s["id"] for s in sections]
        return (
            f"No section matched '{topic}'. "
            f"Available topics: {', '.join(all_ids)}"
        )

    lines = []
    for section in matched:
        lines.append(f"## {section['title']}")
        lines.append(section.get("summary", ""))
        for example in section.get("examples", []):
            lines.append(f"  {example}")
        lines.append("")
    return "\n".join(lines)


def _tool_validate(args: dict) -> str:
    code = args.get("code", "")
    if not code.strip():
        return json.dumps({"syntax_ok": True, "diagnostics": [], "statement_count": 0})

    try:
        from epl.copilot import analyze_code
        result = analyze_code(code)
        return json.dumps(result, default=str)
    except Exception as exc:
        return json.dumps({
            "syntax_ok": False,
            "diagnostics": [{"level": "error", "message": str(exc), "line": None}],
            "statement_count": 0,
            "internal_error": str(exc),
        })


def _tool_run(args: dict) -> str:
    code = args.get("code", "")
    timeout = min(args.get("timeout", 10), 30)

    if not code.strip():
        return json.dumps({"output": "", "error": "No code provided."})

    runner_script = (
        "import sys; "
        "sys.path.insert(0, '.'); "
        "from epl.lexer import Lexer; "
        "from epl.parser import Parser; "
        "from epl.interpreter import Interpreter; "
        "tokens = Lexer(sys.stdin.read()).tokenize(); "
        "program = Parser(tokens).parse(); "
        "Interpreter().execute(program)"
    )

    try:
        epl_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.run(
            [sys.executable, "-c", runner_script],
            input=code,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=epl_dir,
        )
        return json.dumps({
            "output": proc.stdout[:10000] if proc.stdout else "",
            "error": proc.stderr[:5000] if proc.stderr else "",
            "exit_code": proc.returncode,
        })
    except subprocess.TimeoutExpired:
        return json.dumps({
            "output": "",
            "error": f"Execution timed out after {timeout} seconds.",
            "exit_code": -1,
        })
    except Exception as exc:
        return json.dumps({
            "output": "",
            "error": f"Execution failed: {exc}",
            "exit_code": -1,
        })


def _tool_transpile(args: dict) -> str:
    code = args.get("code", "")
    target = args.get("target", "python").lower()

    if not code.strip():
        return json.dumps({"error": "No code provided."})

    try:
        from epl.lexer import Lexer
        from epl.parser import Parser

        tokens = Lexer(code).tokenize()
        program = Parser(tokens).parse()

        if target == "python":
            from epl.python_transpiler import PythonTranspiler
            output = PythonTranspiler().transpile(program)
        elif target == "javascript":
            from epl.js_transpiler import JSTranspiler
            output = JSTranspiler().transpile(program)
        else:
            return json.dumps({"error": f"Unsupported target: {target}. Use 'python' or 'javascript'."})

        return json.dumps({"target": target, "code": output})
    except Exception as exc:
        return json.dumps({"error": f"Transpilation failed: {exc}"})


def _tool_examples(args: dict) -> str:
    query = args.get("query", "").lower()
    if not query:
        return json.dumps({"error": "No query provided."})

    examples_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples"
    )

    if not os.path.isdir(examples_dir):
        return json.dumps({"error": "Examples directory not found.", "path": examples_dir})

    matches = []
    try:
        for fname in sorted(os.listdir(examples_dir)):
            if not fname.endswith(".epl"):
                continue
            fpath = os.path.join(examples_dir, fname)
            if not os.path.isfile(fpath):
                continue

            name_match = query in fname.lower()
            content = ""
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(8192)
            except OSError:
                continue

            content_match = query in content.lower()

            if name_match or content_match:
                matches.append({
                    "file": fname,
                    "code": content[:4000],
                    "match_type": "filename" if name_match else "content",
                })

            if len(matches) >= 5:
                break
    except OSError:
        return json.dumps({"error": "Failed to read examples directory."})

    if not matches:
        return json.dumps({
            "message": f"No examples found matching '{query}'.",
            "hint": "Try broader terms like 'web', 'class', 'loop', 'function'.",
        })

    return json.dumps({"query": query, "results": matches, "count": len(matches)})


def _tool_error_lookup(args: dict) -> str:
    error_input = args.get("error_code", "").strip()
    if not error_input:
        return json.dumps({"error": "No error code provided."})

    try:
        from epl.errors import _HINTS, ERROR_CODES
    except ImportError:
        return json.dumps({"error": "EPL is not installed."})

    code_to_name = {v: k for k, v in ERROR_CODES.items()}
    name_to_code = ERROR_CODES

    error_name = None
    error_code = None

    if error_input.upper().startswith("E") and error_input[1:].isdigit():
        error_code = error_input.upper()
        error_name = code_to_name.get(error_code)
    else:
        for name, code in name_to_code.items():
            if error_input.lower() in name.lower():
                error_name = name
                error_code = code
                break

    if not error_name:
        return json.dumps({
            "error": f"Unknown error: '{error_input}'",
            "available_codes": ERROR_CODES,
        })

    relevant_hints = {
        k: v for k, v in _HINTS.items()
        if error_name.lower().replace("error", "").strip() in k.lower()
        or any(word in k.lower() for word in error_name.lower().split("error")[0].split())
    }

    if not relevant_hints:
        general_hints = dict(list(_HINTS.items())[:3])
        relevant_hints = general_hints

    return json.dumps({
        "error_code": error_code,
        "error_name": error_name,
        "description": f"EPL {error_name} ({error_code})",
        "hints": relevant_hints,
    })


# ── Tool Dispatcher ──────────────────────────────────────────────────

TOOL_HANDLERS = {
    "epl_syntax_reference": _tool_syntax_reference,
    "epl_validate": _tool_validate,
    "epl_run": _tool_run,
    "epl_transpile": _tool_transpile,
    "epl_examples": _tool_examples,
    "epl_error_lookup": _tool_error_lookup,
}


# ── JSON-RPC 2.0 Handler ────────────────────────────────────────────

def _handle_request(request: dict) -> dict | None:
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "epl-mcp-server",
                    "version": _get_version(),
                },
            },
        }

    if method == "notifications/initialized":
        _log("Client initialized successfully.")
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                    "isError": True,
                },
            }

        try:
            result_text = handler(tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                },
            }
        except Exception as exc:
            _log(f"Tool error in {tool_name}: {exc}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Tool error: {exc}"}],
                    "isError": True,
                },
            }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def _get_version() -> str:
    try:
        from epl import __version__
        return __version__
    except ImportError:
        return "unknown"


# ── Main Server Loop ────────────────────────────────────────────────

def main() -> None:
    """Run the EPL MCP server over stdio."""
    _log(f"EPL MCP Server v{_get_version()} starting...")
    _log("Listening on stdin for JSON-RPC 2.0 messages")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            _log(f"Invalid JSON: {exc}")
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()
            continue

        response = _handle_request(request)

        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

    _log("Server shutting down.")


if __name__ == "__main__":
    main()
