"""Shared runtime helpers for EPL CLI and compatibility entrypoints."""

from __future__ import annotations

import os
import re
import sys
from typing import Optional

from epl._debug_log import suppressed as _debug_suppressed
from epl.environment import Environment
from epl.errors import EPLError, set_source_context
from epl.interpreter import Interpreter
from epl.lexer import Lexer
from epl.parser import Parser

CROSS_TARGETS = {
    'windows-x64': 'x86_64-pc-windows-msvc',
    'windows-x86': 'i686-pc-windows-msvc',
    'linux-x64': 'x86_64-unknown-linux-gnu',
    'linux-arm64': 'aarch64-unknown-linux-gnu',
    'macos-x64': 'x86_64-apple-darwin',
    'macos-arm64': 'aarch64-apple-darwin',
    'wasm32': 'wasm32-unknown-wasi',
}


def _offer_ai_explanation(
    error_msg, source_code: Optional[str] = None, use_ai: bool = False
) -> None:
    """Show rich error explanation using the error_explainer module.

    Provides pattern-based diagnostics (always). AI analysis is only used
    when use_ai=True (triggered by --ai-errors flag). By default, the
    explainer runs 100% offline with zero API calls.
    """
    try:
        from epl.error_explainer import explain, format_explanation

        # Accept either an EPLError instance or a plain string
        if isinstance(error_msg, EPLError):
            error = error_msg
        else:
            error = EPLError(str(error_msg))

        exp = explain(error, source=source_code, ai=use_ai)
        print(format_explanation(exp), file=sys.stderr)
    except Exception:
        # Fallback: try the basic AI explain if the explainer fails
        try:
            from epl.ai import explain_error, is_available

            if not is_available():
                return
            print(
                '\n  \u2500 AI Error Explanation \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',
                file=sys.stderr,
            )
            explanation = explain_error(str(error_msg), source_code)
            if explanation:
                for line in explanation.split('\n'):
                    print(f'  {line}', file=sys.stderr)
            print(
                '  \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',
                file=sys.stderr,
            )
        except Exception:
            _debug_suppressed('runtime_support.py:63')
            pass


def run_source(
    source: str,
    interpreter: Optional[Interpreter] = None,
    filename: str = '<input>',
    ai_help: bool = False,
    strict: bool = False,
    safe_mode: bool = False,
    json_errors: bool = False,
) -> bool:
    if interpreter is None:
        interpreter = Interpreter(safe_mode=safe_mode)
    if filename != '<input>':
        interpreter._current_file = os.path.abspath(filename)

    set_source_context(source, filename)

    try:
        program = None
        cache_file = None
        if filename != '<input>' and os.path.isfile(filename):
            from epl.bytecode_cache import cache_path_for
            from epl.bytecode_cache import load as load_cache
            from epl.bytecode_cache import save as save_cache

            cache_file = cache_path_for(filename)
            program = load_cache(source, cache_file)

        if program is None:
            tokens = Lexer(source).tokenize()
            program = Parser(tokens).parse()
            if cache_file is not None:
                try:
                    save_cache(program, source, cache_file)
                except Exception:
                    _debug_suppressed('runtime_support.py:100')
                    pass

        if strict:
            from epl.type_checker import TypeChecker

            checker = TypeChecker(strict=True)
            checker.check(program)
            for warning in checker.warnings:
                if warning.severity == 'warning':
                    print(f'  Warning (line {warning.line}): {warning.message}', file=sys.stderr)
                elif warning.severity == 'info':
                    print(f'  Info (line {warning.line}): {warning.message}', file=sys.stderr)
            if checker.has_errors():
                errors = [warning for warning in checker.warnings if warning.severity == 'error']
                for error in errors:
                    hint = f' (hint: {error.suggestion})' if error.suggestion else ''
                    print(
                        f'  Type Error (line {error.line}): {error.message}{hint}', file=sys.stderr
                    )
                print(
                    f'\n  {len(errors)} type error(s) found. Fix them or run without --strict.',
                    file=sys.stderr,
                )
                return False

        interpreter.execute(program)
        return True
    except EPLError as exc:
        if json_errors:
            print(exc.to_json(), file=sys.stderr)
        else:
            print(f'\n{exc}', file=sys.stderr)
            if ai_help:
                _offer_ai_explanation(str(exc), source, use_ai=True)
            else:
                _offer_ai_explanation(str(exc), source, use_ai=False)
        return False


def run_file(
    filepath: str,
    *,
    strict: bool = False,
    safe_mode: bool = False,
    force_interpret: bool = False,
    json_errors: bool = False,
    ai_errors: bool = False,
) -> bool:
    if not os.path.exists(filepath):
        raise FileNotFoundError(filepath)

    with open(filepath, 'r', encoding='utf-8') as handle:
        source = handle.read()

    if strict:
        from epl.type_checker import TypeChecker

        try:
            program = Parser(Lexer(source).tokenize()).parse()
            checker = TypeChecker(strict=True)
            checker.check(program)
            for warning in checker.warnings:
                if warning.severity in ('warning', 'info'):
                    print(
                        f'  {warning.severity.title()} (line {warning.line}): {warning.message}',
                        file=sys.stderr,
                    )
            if checker.has_errors():
                errors = [warning for warning in checker.warnings if warning.severity == 'error']
                for error in errors:
                    hint = f' (hint: {error.suggestion})' if error.suggestion else ''
                    print(
                        f'  Type Error (line {error.line}): {error.message}{hint}', file=sys.stderr
                    )
                print(
                    f'\n  {len(errors)} type error(s) found. Fix them or run without --strict.',
                    file=sys.stderr,
                )
                return False
        except Exception:
            _debug_suppressed('runtime_support.py:178')
            pass

    # Safe mode (--sandbox) is a security feature implemented ONLY by the
    # interpreter (it blocks file writes/appends, exec, downloads, dir/env
    # mutation, `Use python`, `Load library`, …). The bytecode VM has no
    # safe-mode enforcement, so running sandboxed code on it would silently
    # bypass every restriction. The VM is purely a speed optimization, so when
    # sandboxed we skip it entirely and use the interpreter, which honors the
    # sandbox. (Without this, a fixed VM file-write op executes the very write
    # the sandbox is meant to block.)
    if not force_interpret and not safe_mode:
        from epl.vm import compile_and_run

        # The VM streams output live. If it fails AFTER producing output, the
        # program already had observable effects — silently re-running it on the
        # interpreter would DUPLICATE that output (and any side effects). So we
        # only fall back when the VM produced nothing yet; otherwise we surface
        # the VM error. A pass-through counter preserves live streaming.
        class _CountingStdout:
            def __init__(self, target):
                self._t = target
                self.n = 0

            def write(self, s):
                self.n += len(s)
                return self._t.write(s)

            def flush(self):
                return self._t.flush()

            def __getattr__(self, name):
                return getattr(self._t, name)

        tee = _CountingStdout(sys.stdout)
        saved_stdout = sys.stdout
        sys.stdout = tee
        try:
            compile_and_run(source)
            return True
        except (KeyboardInterrupt, SystemExit, MemoryError):
            raise
        except Exception as exc:
            if tee.n > 0:
                msg = getattr(exc, 'message', None) or str(exc)
                line = getattr(exc, 'line', 0)
                where = f' on line {line}' if line else ''
                print(f'\n  EPL Runtime Error{where}: {msg}', file=sys.stderr)
                return False
            # No output produced yet → safe to fall back to the interpreter.
            if os.environ.get('EPL_VERBOSE') or '--verbose' in sys.argv:
                print(f'  [EPL] VM fallback to interpreter for: {filepath}', file=sys.stderr)
        finally:
            sys.stdout = saved_stdout

    interpreter = Interpreter(safe_mode=safe_mode)
    return run_source(
        source,
        interpreter,
        filepath,
        ai_help=ai_errors,
        strict=strict,
        safe_mode=safe_mode,
        json_errors=json_errors,
    )


def _find_c_compiler() -> Optional[str]:
    import subprocess

    # Only clang is a valid candidate: the native pipeline emits textual LLVM IR
    # (a ``.ll`` file) and links it directly with the C compiler (see the
    # ``[cc, ir_path, ...]`` link command below). gcc cannot consume LLVM IR, so
    # returning it here only produced a confusing "runtime compilation issue"
    # followed by a link failure. Requiring clang lets the caller emit a clear,
    # actionable "install LLVM" message instead.
    candidates = [
        'clang',
        r'C:\Program Files\LLVM\bin\clang.exe',
        r'C:\Program Files (x86)\LLVM\bin\clang.exe',
    ]
    for candidate in candidates:
        try:
            subprocess.run([candidate, '--version'], capture_output=True, timeout=10, check=True)
            return candidate
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
    return None


# EPL types the native backend can lower a function parameter / return value to
# (mirrors Compiler._infer_param_type). Anything outside this set — including an
# untyped parameter — defaults to i8*/string in the backend, which silently
# miscompiles numeric or otherwise-dynamic code.
_NATIVE_TYPES = {
    'integer',
    'int',
    'number',
    'decimal',
    'float',
    'double',
    'text',
    'string',
    'str',
    'boolean',
    'bool',
    'list',
    'array',
    'map',
    'dict',
    'dictionary',
}


def _body_returns_a_value(body) -> bool:
    """True if any statement in ``body`` is a ``Return <expr>`` that yields a
    value. Nested function bodies are skipped — their returns are their own."""
    from epl import ast_nodes as ast

    stack = list(body or [])
    while stack:
        node = stack.pop()
        if node is None or isinstance(node, (str, int, float, bool)):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(node, ast.ReturnStatement):
            if getattr(node, 'value', None) is not None:
                return True
            continue
        if hasattr(node, '__dict__'):
            for attr in vars(node).values():
                if isinstance(attr, list):
                    stack.extend(attr)
                elif hasattr(attr, '__dict__'):
                    stack.append(attr)
    return False


def _native_unsafe_functions(program) -> list:
    """Return ``[(qualified_name, line, reason)]`` for top-level and module
    functions the native backend cannot compile to a provably-correct binary:
    those with an untyped parameter, or a value-returning body with no return
    type. Such functions default to string in the backend and miscompile
    numeric / dynamic code (often into a segfaulting binary). Identifying them
    lets ``epl build`` refuse with an actionable message instead of emitting a
    crashing executable. The default ``epl run`` path handles them correctly."""
    from epl import ast_nodes as ast

    problems: list = []

    def check_fn(fn, qualname: str) -> None:
        reasons: list = []
        unannotated = []  # no type at all
        unsupported = []  # explicit type the backend can't lower
        for param in fn.params:
            if isinstance(param, ast.RestParameter):
                continue
            if isinstance(param, tuple):
                pname = param[0]
                ptype = param[1] if len(param) > 1 else None
            else:
                pname, ptype = getattr(param, 'name', '?'), None
            if ptype is None:
                unannotated.append(pname)
            elif str(ptype).lower() not in _NATIVE_TYPES:
                unsupported.append(f'{pname}: {ptype}')
        if unannotated:
            reasons.append(f'parameter(s) {", ".join(unannotated)} have no type annotation')
        if unsupported:
            reasons.append(
                f'parameter(s) {", ".join(unsupported)} use a type the native '
                'backend cannot compile'
            )
        rt = getattr(fn, 'return_type', None)
        if _body_returns_a_value(fn.body):
            if rt is None:
                reasons.append("returns a value but has no 'and returns <type>' annotation")
            elif str(rt).lower() not in _NATIVE_TYPES:
                reasons.append(f"return type '{rt}' is not one the native backend can compile")
        if reasons:
            problems.append((qualname, getattr(fn, 'line', 0), '; '.join(reasons)))

    def unwrap(node):
        return node.statement if isinstance(node, ast.VisibilityModifier) else node

    for stmt in getattr(program, 'statements', []) or []:
        stmt = unwrap(stmt)
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check_fn(stmt, stmt.name)
        elif isinstance(stmt, ast.ModuleDef):
            for item in stmt.body:
                item = unwrap(item)
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    check_fn(item, f'{stmt.name}::{item.name}')

    return problems


def compile_file(
    filepath: str, opt_level: int = 2, static: bool = False, target: Optional[str] = None
) -> bool:
    if not os.path.exists(filepath):
        raise FileNotFoundError(filepath)

    with open(filepath, 'r', encoding='utf-8') as handle:
        source = handle.read()

    try:
        import subprocess

        from epl.compiler import Compiler

        triple = CROSS_TARGETS.get(target, target) if target else None
        program = Parser(Lexer(source).tokenize()).parse()

        # Safety gate: the native backend has no type inference, so functions
        # with untyped parameters or an untyped value return compile to wrong
        # (often segfaulting) code. Refuse to emit a binary we cannot prove is
        # correct, with an actionable message, rather than shipping a crash.
        unsafe = _native_unsafe_functions(program)
        if unsafe:
            print('\n  Native build cannot guarantee a correct binary for this program.')
            print('  The native compiler needs explicit types; these functions are not')
            print('  fully typed and would miscompile:\n')
            for name, line, reason in unsafe:
                print(f'    - {name} (line {line}): {reason}')
            print('\n  Add type annotations, for example:')
            print('      Function add takes integer a and integer b and returns integer')
            print('\n  ...or run it directly — the interpreter/VM supports full dynamic')
            print('  typing with no annotations required:')
            print(f'      epl run {os.path.basename(filepath)}')
            return False

        compiler = Compiler(opt_level=opt_level, source_filename=filepath)
        if triple:
            compiler.module.triple = triple
        llvm_ir = compiler.compile(program)

        base = os.path.splitext(os.path.basename(filepath))[0]
        if target:
            base += f'_{target.replace("-", "_")}'
        ir_path = base + '.ll'
        with open(ir_path, 'w', encoding='utf-8') as handle:
            handle.write(llvm_ir)

        print('  EPL Compiler — Phase 1 Native Build')
        print(f'  Source: {os.path.basename(filepath)}')
        print(f'  Optimization: O{opt_level}')
        if target:
            print(f'  Target: {target} ({triple})')
        print(f'  LLVM IR written to: {ir_path}')

        script_dir = os.path.dirname(os.path.abspath(__file__))
        runtime_c = os.path.join(script_dir, 'runtime.c')

        if target == 'wasm32':
            wasm_path = base + '.wasm'
            try:
                cmd = [
                    'emcc',
                    ir_path,
                    '-o',
                    wasm_path,
                    f'-O{opt_level}',
                    '-s',
                    'STANDALONE_WASM=1',
                    '-s',
                    'WASM=1',
                ]
                if os.path.exists(runtime_c):
                    cmd.insert(2, runtime_c)
                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
                print(f'\n  Compiled successfully: {wasm_path}')
                return True
            except FileNotFoundError:
                pass
            cc = _find_c_compiler()
            if cc and 'clang' in cc:
                cmd = [
                    cc,
                    '--target=wasm32-wasi',
                    ir_path,
                    '-o',
                    wasm_path,
                    f'-O{opt_level}',
                    '-nostdlib',
                    '-Wl,--no-entry',
                    '-Wl,--export-all',
                ]
                if os.path.exists(runtime_c):
                    cmd.insert(3, runtime_c)
                subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if os.path.exists(wasm_path):
                    print(f'\n  Compiled successfully: {wasm_path}')
                    return True
            print('\n  WASM compilation requires emcc or clang with WASM target.')
            print(f'  LLVM IR saved to: {ir_path}')
            return False

        cc = _find_c_compiler()
        if not cc:
            print('\n  Native build needs the LLVM/clang toolchain (it compiles')
            print('  generated LLVM IR — a plain gcc cannot do this).')
            print('  Install it with:')
            print('    Windows:  winget install LLVM.LLVM')
            print('    macOS:    brew install llvm   (or: xcode-select --install)')
            print('    Linux:    sudo apt install clang   # or your distro equivalent')
            print(f'  The generated LLVM IR was saved to: {ir_path}')
            return False

        if target and 'windows' in target:
            exe_ext = '.exe'
        elif target and 'windows' not in target:
            exe_ext = ''
        elif os.name == 'nt':
            exe_ext = '.exe'
        else:
            exe_ext = ''
        exe_path = base + exe_ext

        rt_obj = base + '_rt.o'
        rt_cmd = [cc, '-c', f'-O{opt_level}', '-o', rt_obj, runtime_c]
        if target:
            rt_cmd.insert(2, f'--target={triple}')
        if os.path.exists(runtime_c):
            print('  Compiling EPL runtime...')
            result = subprocess.run(rt_cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                warning = result.stderr[:200] if result.stderr else ''
                print(f'  Warning: runtime compilation issue: {warning}')

        link_cmd = [cc, ir_path, f'-O{opt_level}', '-o', exe_path]
        if target:
            link_cmd.insert(2, f'--target={triple}')
        if os.path.exists(rt_obj):
            link_cmd.insert(2, rt_obj)
        if static:
            # macOS has no static libc — Apple ships no crt0.o, so `-static`
            # fails at link time with "library 'crt0.o' not found". Silently
            # drop the flag there (the binary is simply dynamically linked)
            # rather than emit an unlinkable command. Targeting a non-Darwin
            # platform from macOS is still allowed to request static linking.
            targeting_macos = (target and triple and 'darwin' in triple) or (
                not target and sys.platform == 'darwin'
            )
            if targeting_macos:
                print('  Note: ignoring -static on macOS (no static libc available)')
            else:
                link_cmd.append('-static')
        if (target and 'windows' not in target) or (not target and os.name != 'nt'):
            link_cmd.append('-lm')
        if target and 'linux' in target:
            link_cmd.extend(['-lpthread', '-ldl'])
        elif not target and os.name != 'nt':
            link_cmd.extend(['-lpthread', '-ldl'])

        print(f'  Linking with: {os.path.basename(cc)}')
        result = subprocess.run(link_cmd, capture_output=True, text=True, timeout=120)

        try:
            os.remove(rt_obj)
        except OSError:
            pass

        if os.path.exists(exe_path):
            size_kb = os.path.getsize(exe_path) / 1024
            print(f'\n  Compiled successfully: {exe_path} ({size_kb:.0f} KB)')
            if not target:
                prefix = '.\\' if os.name == 'nt' else './'
                print(f'  Run it with: {prefix}{exe_path}')
            return True

        print('\n  Compilation failed:')
        if result.stderr:
            for line in result.stderr.strip().split('\n')[:5]:
                print(f'    {line}')
        print(f'  LLVM IR saved to: {ir_path}')
        return False
    except ImportError:
        print('EPL Error: llvmlite not installed.', file=sys.stderr)
        print('Install it with: pip install llvmlite', file=sys.stderr)
        return False
    except Exception as exc:
        print(f'EPL Compilation Error: {exc}', file=sys.stderr)
        return False


def _bare_repl(interpreter: Interpreter) -> None:
    print("  EPL REPL (plain mode) — type 'exit' to quit")
    history: list = []
    session_lines: list = []
    while True:
        try:
            line = input('EPL> ')
        except (EOFError, KeyboardInterrupt):
            print('\nGoodbye!')
            break
        line = line.strip()
        if not line:
            continue
        if line.lower() in ('exit', 'quit'):
            print('Goodbye!')
            break
        if line.startswith('.'):
            handle_repl_command(line, history, session_lines, interpreter)
            continue
        source = line
        open_blocks = count_open_blocks(source)
        while open_blocks > 0:
            try:
                continuation = input('...  ')
            except (EOFError, KeyboardInterrupt):
                source = ''
                break
            source += '\n' + continuation
            open_blocks = count_open_blocks(source)
        if source:
            history.append(source)
            session_lines.append(source)
            run_source(source, interpreter, '<repl>')


def run_repl() -> None:
    interpreter = Interpreter()
    try:
        from epl.repl import start_rich_repl

        start_rich_repl(
            run_source_fn=run_source,
            count_open_blocks_fn=count_open_blocks,
            handle_command_fn=handle_repl_command,
            interpreter=interpreter,
        )
    except Exception:
        _bare_repl(interpreter)


def handle_repl_command(cmd: str, history, session_lines, interpreter) -> None:
    parts = cmd.split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ''

    if command == '.help':
        print('  REPL Commands:')
        print('    .help              Show this help')
        print('    .clear             Clear all variables')
        print('    .history           Show command history')
        print('    .load <file>       Load and run an EPL file')
        print('    .save <file>       Save session to file')
        print('    .vars              Show defined variables')
        print('    .run <code>        Run a quick expression')
        print('    .type <expr>       Show the type of a value')
        print('    .time <code>       Time code execution')
        print('    .fmt               Format last block')
        print('    .lint              Lint session code')
        print('    .export <file>     Export session as formatted EPL')
        print('    .profile <code>    Profile code execution')
        print('    exit / quit        Exit the REPL')
    elif command == '.clear':
        interpreter.global_env = Environment(name='global')
        interpreter.output_lines = []
        interpreter._constants = set()
        interpreter._imported_files = set()
        interpreter._template_cache = {}
        session_lines.clear()
        print('  Environment cleared.')
    elif command == '.history':
        if not history:
            print('  No history yet.')
        else:
            for index, entry in enumerate(history[-20:], 1):
                preview = entry.replace('\n', ' \\ ')
                if len(preview) > 70:
                    preview = preview[:67] + '...'
                print(f'  {index:3d}. {preview}')
    elif command == '.load':
        if not arg:
            print('  Usage: .load <filename.epl>')
        elif not os.path.exists(arg):
            print(f'  File not found: {arg}')
        else:
            with open(arg, 'r', encoding='utf-8') as handle:
                source = handle.read()
            session_lines.append(f'# loaded from {arg}')
            session_lines.append(source)
            print(f'  Loading {arg}...')
            run_source(source, interpreter, arg)
    elif command == '.save':
        if not arg:
            print('  Usage: .save <filename.epl>')
        else:
            with open(arg, 'w', encoding='utf-8') as handle:
                handle.write('\n'.join(session_lines) + '\n')
            print(f'  Session saved to {arg}')
    elif command == '.vars':
        env = getattr(interpreter, 'global_env', None)
        values = getattr(env, 'variables', None)
        if not values:
            print('  No variables defined.')
        else:
            for name, slot in sorted(values.items()):
                value = slot['value'] if isinstance(slot, dict) and 'value' in slot else slot
                rendered = repr(value) if not isinstance(value, str) else f'"{value}"'
                if len(rendered) > 60:
                    rendered = rendered[:57] + '...'
                print(f'  {name} = {rendered}')
    elif command == '.run':
        if arg:
            run_source(arg, interpreter, '<repl>')
        else:
            print('  Usage: .run <EPL expression>')
    elif command == '.type':
        if arg:
            try:
                program = Parser(Lexer(f'Print type_of({arg})').tokenize()).parse()
                temp_interp = Interpreter()
                src_env = getattr(interpreter, 'global_env', None)
                if src_env is not None and getattr(src_env, 'variables', None):
                    for name in src_env.variables:
                        temp_interp.global_env.define_variable(name, src_env.get_variable(name))
                temp_interp.execute(program)
                for line in temp_interp.output_lines:
                    print(f'  {line}')
            except Exception as exc:
                print(f'  Type error: {exc}')
        else:
            print('  Usage: .type <expression>')
    elif command == '.time':
        if arg:
            import time as _time

            started = _time.perf_counter()
            run_source(arg, interpreter, '<repl>')
            elapsed = (_time.perf_counter() - started) * 1000
            print(f'  Executed in {elapsed:.2f} ms')
        else:
            print('  Usage: .time <EPL code>')
    elif command == '.fmt':
        if session_lines:
            try:
                from epl.formatter import format_source

                formatted = format_source('\n'.join(session_lines))
                print('  Formatted session:')
                for line in formatted.split('\n'):
                    print(f'    {line}')
            except Exception as exc:
                print(f'  Format error: {exc}')
        else:
            print('  No session code to format.')
    elif command == '.lint':
        if session_lines:
            try:
                from epl.doc_linter import LintConfig, Linter

                issues = Linter(LintConfig()).lint_source('\n'.join(session_lines), '<repl>')
                if issues:
                    print(Linter(LintConfig()).format_report(issues))
                else:
                    print('  No lint issues found!')
            except Exception as exc:
                print(f'  Lint error: {exc}')
        else:
            print('  No session code to lint.')
    elif command == '.export':
        if not arg:
            print('  Usage: .export <filename.epl>')
        elif session_lines:
            try:
                from epl.formatter import format_source

                with open(arg, 'w', encoding='utf-8') as handle:
                    handle.write(format_source('\n'.join(session_lines)))
                print(f'  Exported formatted session to {arg}')
            except Exception as exc:
                print(f'  Export error: {exc}')
        else:
            print('  No session code to export.')
    elif command == '.profile':
        if arg:
            try:
                import time as _time

                from epl.profiler import get_profiler

                profiler = get_profiler()
                profiler.reset()
                profiler.enable()
                started = _time.perf_counter()
                run_source(arg, interpreter, '<repl>')
                elapsed = (_time.perf_counter() - started) * 1000
                profiler.disable()
                print(f'  Total: {elapsed:.2f} ms')
                report = profiler.report()
                if 'TOTAL' in report:
                    print(report)
            except Exception as exc:
                print(f'  Profile error: {exc}')
        else:
            print('  Usage: .profile <EPL code>')
    else:
        print(f'  Unknown command: {command}. Type .help for available commands.')


def count_open_blocks(source: str) -> int:
    stripped = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', source)
    stripped = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", stripped)

    openers = 0
    closers = 0
    for line in stripped.lower().split('\n'):
        statement = line.strip()
        if statement.startswith('#') or statement.startswith('//') or statement.startswith('note:'):
            continue
        if re.match(r'if\s+', statement):
            openers += 1
        if re.match(r'while\s+', statement):
            openers += 1
        if re.match(r'repeat\s+', statement):
            openers += 1
        if re.match(r'for\s+each\s+', statement):
            openers += 1
        if re.match(r'for\s+', statement) and not re.match(r'for\s+each\s+', statement):
            openers += 1
        if re.match(r'(define\s+)?function\s+', statement):
            openers += 1
        if re.match(r'class\s+', statement):
            openers += 1
        if re.match(r'try', statement):
            openers += 1
        if re.match(r'match\s+', statement):
            openers += 1
        if re.match(r'noteblock', statement):
            openers += 1
        if re.match(r'async\s+function\s+', statement):
            openers += 1
        if re.match(r'end\b', statement):
            closers += 1

    return max(0, openers - closers)
