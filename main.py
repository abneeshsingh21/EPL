"""EPL entry point — thin compatibility shim.

This module re-exports the authoritative implementations from epl.runtime_support
and epl.cli. Tests and legacy scripts that ``import main`` continue to work.
"""

from __future__ import annotations

import os
import sys

# ── Re-exports expected by the test suite ──────────────────────────────
from epl.errors import set_source_context  # noqa: F401
from epl.interpreter import Interpreter  # noqa: F401
from epl.lexer import Lexer  # noqa: F401
from epl.parser import Parser  # noqa: F401
from epl.runtime_support import CROSS_TARGETS, compile_file  # noqa: F401


# ── Convenience generators (test_phase6 & test_tier4) ───────────────────

def _compile_to_wasm(filepath: str, opt_level: int = 2) -> bool:
    """Legacy compatibility stub for WASM compilation."""
    from epl.runtime_support import compile_file
    return compile_file(filepath, opt_level=opt_level, target='wasm32')

def generate_desktop(program, output_dir, app_name='EPLApp'):
    """Generate a desktop (Jetpack Compose) project."""
    from epl.desktop import generate_desktop_project
    return generate_desktop_project(program, output_dir, app_name=app_name)


def generate_web(program, output_dir, app_name='EPLWeb', mode='js'):
    """Generate a web project (JS, WASM, or Kotlin/JS)."""
    from epl.wasm_web import generate_web_project
    return generate_web_project(program, output_dir, app_name=app_name, mode=mode)


def generate_android(program, output_dir, app_name='EPLApp'):
    """Generate an Android project."""
    from epl.kotlin_gen import generate_android_project
    return generate_android_project(program, output_dir)


# ── Serve command (test_correctness_hardening) ─────────────────────────

def _run_serve_command(argv):
    """Parse --host / --port / --workers flags and start the EPL web server.

    Defaults host to 127.0.0.1 (safe). Warns when 0.0.0.0 is used and when
    unknown flags are passed.
    """
    host = '127.0.0.1'
    port = 8000
    workers = 4
    filepath = None
    unknown_flags = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == '--host' and i + 1 < len(argv):
            host = argv[i + 1]
            i += 2
            continue
        elif arg == '--port' and i + 1 < len(argv):
            port = int(argv[i + 1])
            i += 2
            continue
        elif arg == '--workers' and i + 1 < len(argv):
            workers = int(argv[i + 1])
            i += 2
            continue
        elif arg.startswith('--'):
            unknown_flags.append(arg)
            i += 1
            continue
        elif filepath is None:
            filepath = arg
        i += 1

    # Warn on unknown flags
    for flag in unknown_flags:
        print(f'WARNING: Unknown flag: {flag}', file=sys.stderr)

    # Warn on 0.0.0.0
    if host == '0.0.0.0':
        print(
            'WARNING: Binding to 0.0.0.0 exposes this server to all network interfaces. '
            'Use --host 127.0.0.1 for local-only access.',
            file=sys.stderr,
        )

    if not filepath or not os.path.exists(filepath):
        print('Error: EPL file not found.', file=sys.stderr)
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    set_source_context(source, filepath)
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    interp = Interpreter()
    interp.execute(program)

    wsgi_app = None
    if hasattr(interp, '_web_app') and interp._web_app:
        from epl.deploy import WSGIAdapter
        wsgi_app = WSGIAdapter(interp._web_app, interp)

    from epl.deploy import serve as deploy_serve
    deploy_serve(wsgi_app, host=host, port=port, workers=workers)


# ── Main entry point ──────────────────────────────────────────────────

def main():
    """Delegate to the authoritative CLI dispatcher."""
    from epl.cli import cli_main
    cli_main()


if __name__ == '__main__':
    main()
