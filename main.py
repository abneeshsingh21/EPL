"""EPL entry point — thin compatibility shim.

This module re-exports the authoritative implementations from epl.runtime_support
and epl.cli. Tests and legacy scripts that ``import main`` continue to work.
"""

from __future__ import annotations

import os
import sys

# ── Re-exports expected by the test suite ──────────────────────────────
from epl.errors import (
    EPLError,  # noqa: F401
    set_source_context,  # noqa: F401
)
from epl.interpreter import Interpreter  # noqa: F401
from epl.lexer import Lexer  # noqa: F401
from epl.parser import Parser  # noqa: F401
from epl.runtime_support import (  # noqa: F401
    CROSS_TARGETS,
    compile_file,
    count_open_blocks,  # noqa: F401
)
from epl.runtime_support import handle_repl_command as _handle_repl_command  # noqa: F401
from epl.runtime_support import run_repl as _shared_run_repl  # noqa: F401

# ── Convenience generators (test_phase6 & test_tier4) ───────────────────


def _compile_to_wasm(filepath: str, opt_level: int = 2) -> bool:
    """Legacy compatibility stub for WASM compilation."""
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


def _read_source(filepath):
    if not os.path.exists(filepath):
        print(f'EPL Error: File not found: {filepath}', file=sys.stderr)
        sys.exit(1)
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def _parse_source(source):
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def transpile_micropython(filepath, target='esp32'):
    source = _read_source(filepath)
    try:
        from epl.micropython_transpiler import transpile_to_micropython

        program = _parse_source(source)
        mpy = transpile_to_micropython(program, target=target)
        out = os.path.splitext(os.path.basename(filepath))[0] + f'_{target}_mpy.py'
        with open(out, 'w', encoding='utf-8') as f:
            f.write(mpy)
    except Exception as e:
        print(f'EPL Error: {e}', file=sys.stderr)
        sys.exit(1)


def run_benchmark(filepath, runs=5, warmup=1):
    source = _read_source(filepath)
    import time as _time

    try:
        from epl.vm import compile_and_run

        for _ in range(warmup):
            compile_and_run(source)
        times = []
        for _ in range(runs):
            t0 = _time.perf_counter()
            compile_and_run(source)
            times.append(_time.perf_counter() - t0)
    except Exception as e:
        print(f'EPL Error: {e}', file=sys.stderr)
        sys.exit(1)


def run_profiler(filepath, extra_args):
    source = _read_source(filepath)
    import time as _time

    trace_file = None
    top_n = 20
    i = 0
    while i < len(extra_args):
        if extra_args[i] == '--trace' and i + 1 < len(extra_args):
            trace_file = extra_args[i + 1]
            i += 2
        elif extra_args[i] == '--top' and i + 1 < len(extra_args):
            top_n = int(extra_args[i + 1])
            i += 2
        else:
            i += 1

    try:
        from epl.profiler import get_profiler

        profiler = get_profiler()
        profiler.reset()
        profiler.enable()

        t0 = _time.perf_counter()
        set_source_context(source, filepath)
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        interp = Interpreter()
        interp.execute(program)

        total_time = (_time.perf_counter() - t0) * 1000
        profiler.disable()

        stats = profiler.get_stats()
        if trace_file:
            profiler.export_trace(trace_file)

    except Exception as e:
        print(f'Profiler Error: {e}', file=sys.stderr)
        sys.exit(1)


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


def _force_interpret():
    """Check if --interpret flag was passed (evaluated lazily, not at import)."""
    return '--interpret' in sys.argv


def legacy_main(argv=None):
    """Legacy command dispatcher retained while commands move into epl.cli."""
    from epl.cli import cli_main

    return cli_main(list(sys.argv[1:] if argv is None else argv))


def main(argv=None):
    """Authoritative source-checkout entry point backed by epl.cli."""
    from epl.cli import cli_main

    return cli_main(argv)


if __name__ == '__main__':
    main()


def run_repl():
    """Compatibility wrapper over the shared EPL runtime implementation."""
    _shared_run_repl()


def run_debugger(filepath, extra_args):
    """Run the EPL debugger on a file."""
    source = _read_source(filepath)
    try:
        from epl.debugger import DebugInterpreter, EPLDebugger

        debugger = EPLDebugger()

        # Parse -b flags for initial breakpoints
        i = 0
        while i < len(extra_args):
            if extra_args[i] == '-b' and i + 1 < len(extra_args):
                bp = extra_args[i + 1]
                try:
                    debugger.add_breakpoint(int(bp))
                except ValueError:
                    debugger.add_breakpoint(bp)  # function name
                i += 2
            else:
                i += 1

        interp = DebugInterpreter(debugger)
        debugger.source_code = source
        debugger.source_lines = source.split('\n')

        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()

        print(f'  EPL Debugger — {filepath}')
        print(f'  Breakpoints: {len(debugger.breakpoints)}')
        print("  Type 'help' for commands, 'c' to continue\n")
        interp.execute(program)

    except EPLError as e:
        print(f'\n{e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Debugger Error: {e}', file=sys.stderr)
        sys.exit(1)


def run_linter(targets):
    """Lint EPL source files."""
    try:
        from epl.doc_linter import LintConfig, Linter

        fix_mode = '--fix' in targets
        targets = [t for t in targets if t != '--fix']
        if not targets:
            targets = ['.']

        config = LintConfig()
        linter = Linter(config)
        all_issues = []

        for target in targets:
            if os.path.isdir(target):
                all_issues.extend(linter.lint_directory(target))
            elif os.path.isfile(target):
                all_issues.extend(linter.lint_file(target))
            else:
                print(f'  Not found: {target}')

        if fix_mode:
            fix_total = 0
            for target in targets:
                if os.path.isfile(target):
                    _, count = linter.auto_fix(target)
                    fix_total += count
                elif os.path.isdir(target):
                    from pathlib import Path

                    for fpath in Path(target).glob('**/*.epl'):
                        _, count = linter.auto_fix(str(fpath))
                        fix_total += count
            print(f'  Fixed {fix_total} issues')
        else:
            print(linter.format_report(all_issues))
            errors = sum(1 for i in all_issues if i.severity == 'error')
            if errors:
                sys.exit(1)

    except Exception as e:
        print(f'Lint Error: {e}', file=sys.stderr)
        sys.exit(1)


def format_epl_source(source, tab_size=4):
    """Format EPL source code with proper indentation (delegates to epl.formatter)."""
    from epl.formatter import format_source

    return format_source(source, tab_size=tab_size)


def run_formatter(args):
    """Format EPL source files."""
    check_only = '--check' in args
    in_place = '--in-place' in args
    files = [a for a in args if not a.startswith('--')]

    if not files:
        print('Usage: python main.py fmt <file.epl> [--check] [--in-place]', file=sys.stderr)
        sys.exit(1)

    import glob

    targets = []
    for f in files:
        if os.path.isdir(f):
            targets.extend(glob.glob(os.path.join(f, '**', '*.epl'), recursive=True))
        else:
            targets.append(f)

    any_changed = False
    for filepath in targets:
        if not os.path.isfile(filepath):
            print(f'File not found: {filepath}', file=sys.stderr)
            continue
        with open(filepath, 'r', encoding='utf-8') as fh:
            original = fh.read()
        formatted = format_epl_source(original)
        if formatted != original:
            any_changed = True
            if check_only:
                print(f'  NEEDS FORMATTING: {filepath}')
            elif in_place:
                with open(filepath, 'w', encoding='utf-8') as fh:
                    fh.write(formatted)
                print(f'  FORMATTED: {filepath}')
            else:
                print(formatted)
        else:
            if not check_only:
                print(f'  OK: {filepath}')

    if check_only and any_changed:
        sys.exit(1)


def run_lsp_server():
    """Start the EPL Language Server Protocol server."""
    try:
        from epl.lsp_server import EPLLanguageServer

        tcp_mode = '--tcp' in sys.argv
        if tcp_mode:
            port = 2087
            for i, arg in enumerate(sys.argv):
                if arg == '--port' and i + 1 < len(sys.argv):
                    port = int(sys.argv[i + 1])
            print(f'  EPL Language Server starting on TCP port {port}...')
            print(f'  Connect your IDE to localhost:{port}')
            server = EPLLanguageServer()
            server.start_tcp(port)
        else:
            # stdio mode (default for VS Code)
            server = EPLLanguageServer()
            server.start_stdio()

    except Exception as e:
        print(f'LSP Error: {e}', file=sys.stderr)
        sys.exit(1)
