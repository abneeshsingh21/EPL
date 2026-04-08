"""
EPL - English Programming Language (v7.0)
Production-ready command-line entry point.

Usage:
    python main.py <file.epl>               Run an EPL file (interpret)
    python main.py compile <file.epl>       Compile to native executable
    python main.py ir <file.epl>            Show LLVM IR (debug)
    python main.py js <file.epl>            Transpile to JavaScript
    python main.py node <file.epl>          Transpile to Node.js
    python main.py kotlin <file.epl>        Transpile to Kotlin
    python main.py python <file.epl>        Transpile to Python
    python main.py android <file.epl>       Generate Android project
    python main.py playground               Start Web Playground IDE
    python main.py notebook                 Start Notebook (Jupyter-like)
    python main.py blocks                   Start Visual Block Editor
    python main.py copilot                  AI Copilot (describe -> code)
    python main.py gui <file.epl>           Run with GUI support
    python main.py gen <description>        AI-generate EPL code from description
    python main.py explain <file.epl>       AI-explain what code does
    python main.py init                     Initialize new project
    python main.py install <package>        Install a package
    python main.py gitinstall <owner/repo>  Install/save a GitHub package dependency
    python main.py gitremove <name>         Remove a GitHub dependency declaration
    python main.py gitdeps                  List declared GitHub dependencies
    python main.py pyinstall <import> [spec] Install/save a Python package
    python main.py pyremove <import>        Remove a Python package declaration
    python main.py pydeps                   List declared Python dependencies
    python main.py github <cmd>             Clone/pull/push GitHub projects
    python main.py uninstall <package>      Remove a package
    python main.py packages                 List installed packages
    python main.py ai <prompt>              AI code assistant
    python main.py train                    Train EPL AI model (Ollama)
    python main.py model                    Manage AI models
    python main.py vm <file.epl>            Run with bytecode VM (fast)
    python main.py package <file.epl>       Package as standalone executable
    python main.py build <file.epl>         Alias for package
    python main.py deploy [options]         Generate deployment configs
    python main.py serve <file.epl>         Start production server (auto-detects platform)
        --port N                              Server port (default: 8000)
        --workers N                           Number of workers (default: 4)
        --reload                              Enable hot-reload (dev mode)
        --store memory|sqlite|redis           Store backend (default: memory)
        --session memory|sqlite|redis         Session backend (default: memory)
"""

import sys
import os

# Python version guard
if sys.version_info < (3, 9):
    print(f"EPL requires Python 3.9 or later (found {sys.version_info.major}.{sys.version_info.minor}).")
    print("Please upgrade Python: https://python.org/downloads/")
    sys.exit(1)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.environment import Environment
from epl.errors import EPLError
from epl.errors import set_source_context
from epl import __version__ as VERSION
from epl.runtime_support import (
    CROSS_TARGETS as SHARED_CROSS_TARGETS,
    compile_file as _shared_compile_file,
    count_open_blocks as _shared_count_open_blocks,
    handle_repl_command as _shared_handle_repl_command,
    run_file as _shared_run_file,
    run_repl as _shared_run_repl,
    run_source as _shared_run_source,
)

# Phase 5: detect --interpret for direct compatibility helpers without mutating
# sys.argv before the authoritative epl.cli entrypoint sees it.
_FORCE_INTERPRET = '--interpret' in sys.argv


def _run_serve_command(args):
    """Parse serve command args and start production server."""
    filename = args[0]
    port = 8000
    workers = 4
    reload_mode = False
    store_backend = 'memory'
    session_backend = 'memory'

    i = 1
    while i < len(args):
        if args[i] == '--port' and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        elif args[i] == '--workers' and i + 1 < len(args):
            workers = int(args[i + 1])
            i += 2
        elif args[i] == '--reload':
            reload_mode = True
            i += 1
        elif args[i] == '--store' and i + 1 < len(args):
            store_backend = args[i + 1]
            i += 2
        elif args[i] == '--session' and i + 1 < len(args):
            session_backend = args[i + 1]
            i += 2
        else:
            i += 1

    # Parse and execute EPL file to build the app
    if not os.path.isfile(filename):
        print(f"Error: File not found: {filename}", file=sys.stderr)
        sys.exit(1)

    with open(filename, 'r', encoding='utf-8') as f:
        source = f.read()

    set_source_context(source, filename)
    interpreter = Interpreter()
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interpreter.execute(program)

    # Get the web app from interpreter
    app = getattr(interpreter, '_web_app', None)
    if app is None:
        print("Error: No web app found in EPL file. Use 'Create App ...' in your .epl file.", file=sys.stderr)
        sys.exit(1)

    # Configure backends
    from epl.store_backends import configure_backends
    configure_backends(store=store_backend, session=session_backend)

    # Start production server
    from epl.deploy import serve, WSGIAdapter
    wsgi_app = WSGIAdapter(app, interpreter)
    serve(wsgi_app, host='0.0.0.0', port=port, workers=workers, reload=reload_mode)


def run_source(source: str, interpreter: Interpreter = None, filename: str = "<input>", ai_help: bool = False, strict: bool = False, safe_mode: bool = False, json_errors: bool = False):
    """Compatibility wrapper over the shared EPL runtime implementation."""
    return _shared_run_source(
        source,
        interpreter=interpreter,
        filename=filename,
        ai_help=ai_help,
        strict=strict,
        safe_mode=safe_mode,
        json_errors=json_errors,
    )


def _offer_ai_explanation(error_msg, source_code=None):
    """Compatibility shim retained for older imports."""
    try:
        from epl.runtime_support import _offer_ai_explanation as _shared_offer_ai_explanation

        _shared_offer_ai_explanation(error_msg, source_code)
    except Exception:
        pass


def run_file(filepath: str, strict: bool = False, safe_mode: bool = False, force_interpret: bool = False, json_errors: bool = False):
    """Compatibility wrapper over the shared EPL runtime implementation."""
    try:
        ok = _shared_run_file(
            filepath,
            strict=strict,
            safe_mode=safe_mode,
            force_interpret=force_interpret or _FORCE_INTERPRET,
            json_errors=json_errors,
        )
    except FileNotFoundError:
        print(f"EPL Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    if not ok:
        sys.exit(1)


CROSS_TARGETS = SHARED_CROSS_TARGETS

def _find_c_compiler():
    """Find a working C compiler (clang preferred, then gcc)."""
    import subprocess
    candidates = [
        'clang',
        r'C:\Program Files\LLVM\bin\clang.exe',
        r'C:\Program Files (x86)\LLVM\bin\clang.exe',
        'gcc',
    ]
    for cc in candidates:
        try:
            subprocess.run([cc, '--version'], capture_output=True, timeout=10)
            return cc
        except (FileNotFoundError, Exception):
            continue
    return None


def compile_file(filepath: str, opt_level: int = 2, static: bool = False, target: str = None):
    """Compatibility wrapper over the shared EPL runtime implementation."""
    try:
        return _shared_compile_file(filepath, opt_level=opt_level, static=static, target=target)
    except FileNotFoundError:
        print(f"EPL Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)


def _compile_to_wasm(filepath: str):
    """Compile an EPL file to WebAssembly (.wasm)."""
    if not os.path.exists(filepath):
        print(f"EPL Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        from epl.compiler import Compiler

        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()

        compiler = Compiler()
        base = os.path.splitext(os.path.basename(filepath))[0]
        wasm_path = compiler.compile_to_wasm(program, output_path=base)
        print(f"  WebAssembly compiled: {wasm_path}")

    except ImportError:
        print("EPL Error: llvmlite not installed.", file=sys.stderr)
        print("Install it with: pip install llvmlite", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"EPL WASM Error: {e}", file=sys.stderr)
        sys.exit(1)


def show_ir(filepath: str):
    """Show the LLVM IR for an EPL file."""
    if not os.path.exists(filepath):
        print(f"EPL Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        from epl.compiler import Compiler

        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()

        compiler = Compiler()
        ir_code = compiler.get_ir(program)
        print(ir_code)

    except ImportError:
        print("EPL Error: llvmlite not installed.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"EPL Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_repl():
    """Compatibility wrapper over the shared EPL runtime implementation."""
    _shared_run_repl()


def _bare_repl(interpreter):
    """Compatibility wrapper retained for older imports."""
    from epl.runtime_support import _bare_repl as _shared_bare_repl

    _shared_bare_repl(interpreter)


def _handle_repl_command(cmd, history, session_lines, interpreter):
    """Compatibility wrapper over the shared EPL runtime implementation."""
    _shared_handle_repl_command(cmd, history, session_lines, interpreter)


def count_open_blocks(source: str) -> int:
    """Compatibility wrapper over the shared EPL runtime implementation."""
    return _shared_count_open_blocks(source)


def legacy_main(argv=None):
    """Legacy command dispatcher retained while commands move into epl.cli."""
    compatibility_commands = ('resolve', 'workspace', 'ci', 'sync-index')
    _ = compatibility_commands

    from epl.cli import cli_main

    return cli_main(list(sys.argv[1:] if argv is None else argv))

    # Extract global flags
    args = list(sys.argv[1:] if argv is None else argv)
    force_interpret = '--interpret' in args
    if force_interpret:
        args = [a for a in args if a != '--interpret']
    strict = '--strict' in args
    if strict:
        args = [a for a in args if a != '--strict']

    no_color = '--no-color' in args or os.environ.get('NO_COLOR')
    if no_color:
        args = [a for a in args if a != '--no-color']
        os.environ['NO_COLOR'] = '1'

    verbose = '--verbose' in args
    if verbose:
        args = [a for a in args if a != '--verbose']

    quiet = '--quiet' in args
    if quiet:
        args = [a for a in args if a != '--quiet']

    sandbox = '--sandbox' in args
    if sandbox:
        args = [a for a in args if a != '--sandbox']

    json_errors = '--json' in args and (not args or args[0] != 'bench')
    if json_errors:
        args = [a for a in args if a != '--json']

    # Configure logging level
    import logging
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format='%(name)s: %(message)s')
    elif quiet:
        logging.basicConfig(level=logging.ERROR, format='%(message)s')
    else:
        logging.basicConfig(level=logging.WARNING, format='%(message)s')

    if len(args) > 0:
        command = args[0]

        if command in ('--help', '-h'):
            print(f"EPL - English Programming Language v{VERSION}")
            print()
            print("Usage:")
            print("  python main.py <file.epl>               Run (VM default, fast)")
            print("  python main.py <file.epl> --interpret    Run with tree-walker interpreter")
            print("  python main.py compile <file.epl>       Compile to .exe (LLVM)")
            print("  python main.py wasm <file.epl>          Compile to WebAssembly (.wasm)")
            print("  python main.py ir <file.epl>            Show LLVM IR")
            print("  python main.py js <file.epl>            Transpile to JavaScript")
            print("  python main.py node <file.epl>          Transpile to Node.js")
            print("  python main.py kotlin <file.epl>        Transpile to Kotlin")
            print("  python main.py python <file.epl>        Transpile to Python")
            print("  python main.py micropython <file.epl>   Transpile to MicroPython (ESP32/Pico)")
            print("  python main.py android <file.epl>       Generate Android project")
            print("  python main.py playground               Start Web Playground IDE")
            print("  python main.py notebook                 Start Notebook (Jupyter-like)")
            print("  python main.py blocks                   Start Visual Block Editor")
            print("  python main.py copilot                  AI Copilot (describe -> code)")
            print("  python main.py gen <description>        AI-generate EPL code")
            print("  python main.py explain <file.epl>       AI-explain code")
            print("  python main.py init                     Initialize new project")
            print("  python main.py install <package>        Install a package")
            print("  python main.py gitinstall <owner/repo>  Install/save a GitHub package dependency")
            print("  python main.py gitremove <name>         Remove a GitHub dependency declaration")
            print("  python main.py gitdeps                  List declared GitHub dependencies")
            print("  python main.py pyinstall <import> [spec] Install/save a Python package")
            print("  python main.py pyremove <import>        Remove a Python dependency declaration")
            print("  python main.py pydeps                   List declared Python dependencies")
            print("  python main.py github <cmd>             Clone/pull/push GitHub projects")
            print("  python main.py uninstall <package>      Remove a package")
            print("  python main.py packages                 List installed packages")
            print("  python main.py search <query>           Search package registry")
            print("  python main.py publish [path]           Publish package to registry")
            print("  python main.py info <package>           Show package details")
            print("  python main.py stats                    Show download statistics")
            print("  python main.py site [dir]               Generate documentation site")
            print("  python main.py ai <prompt>              AI code assistant (cloud/local)")
            print("  python main.py cloud                    Configure cloud AI (Groq)")
            print("  python main.py train                    Train EPL AI model (Ollama)")
            print("  python main.py model                    Manage AI models")
            print("  python main.py debug <file.epl>         Debug with breakpoints")
            print("  python main.py test [dir|file]           Run EPL tests")
            print("  python main.py lint [dir|file]           Lint source code")
            print("  python main.py docs [dir|file]           Generate API docs")
            print("  python main.py fmt <file.epl>            Format EPL source code")
            print("  python main.py deploy <target>          Generate production deploy configs")
            print("  python main.py serve <file.epl>          Start production server")
            print("  python main.py lsp                      Start LSP server")
            print("  python main.py vm <file.epl>            Run with bytecode VM (explicit)")
            print("  python main.py benchmark <file.epl>     Benchmark VM vs interpreter")
            print("  python main.py profile <file.epl>       Profile execution (function timing)")
            print("  python main.py bench                    Run benchmark suite")
            print("  python main.py package <file.epl>       Package as standalone exe")
            print("  python main.py resolve                  Resolve all dependencies (backtracking)")
            print("  python main.py workspace <cmd>          Workspace/monorepo commands")
            print("  python main.py ci [generate|preview]    Generate CI workflows")
            print("  python main.py sync-index [--force]     Sync package index")
            print("  python main.py                          Interactive REPL")
            print()
            print("Flags:")
            print("  --interpret    Force tree-walking interpreter (skip VM)")
            print("  --strict       Enable static type checking before execution")
            print("  --no-color     Disable colored output")
            print("  --verbose      Show debug-level diagnostic output")
            print("  --quiet        Suppress all output except errors")
            print("  --sandbox      Disable dangerous builtins (exec, file ops, network)")
            print("  --json         Output errors as JSON (for tool integration)")
            print()
            print("Examples:")
            print("  python main.py examples/advanced.epl")
            print("  python main.py compile examples/advanced.epl")
            print("  python main.py js examples/hello.epl")
            print("  python main.py install github:user/repo")
            print("  python main.py install user/repo")
            print("  python main.py gitinstall epl-lang/web-kit web-kit")
            print("  python main.py pyinstall yaml pyyaml>=6")
            print("  python main.py github clone epl-lang/epl")
            print('  python main.py github push . -m "Update project"')
            print('  python main.py ai "write a fibonacci function"')
            print('  python main.py gen "calculator program"')
            print("  python main.py cloud --setup               # setup Groq (free, fast)")
            print("  python main.py train                       # create local AI model")
            print("  python main.py train --base qwen3:4b       # use a specific base")
            return

        if command in ('--version', '-v'):
            print(f"EPL v{VERSION}")
            return

        if command == 'compile':
            if len(args) < 2:
                print("Usage: python main.py compile <file.epl> [--opt 0|1|2|3] [--static] [--target <target>]", file=sys.stderr)
                print("  Targets: " + ", ".join(sorted(CROSS_TARGETS.keys())), file=sys.stderr)
                sys.exit(1)
            opt_level = 2
            static_link = False
            target = None
            i = 2
            while i < len(args):
                if args[i] == '--opt' and i + 1 < len(args):
                    opt_level = int(args[i + 1])
                    i += 2
                elif args[i] == '--static':
                    static_link = True
                    i += 1
                elif args[i] == '--target' and i + 1 < len(args):
                    target = args[i + 1]
                    i += 2
                else:
                    i += 1
            return 0 if compile_file(args[1], opt_level=opt_level, static=static_link, target=target) else 1

        if command == 'ir':
            if len(args) < 2:
                print("Usage: python main.py ir <file.epl>", file=sys.stderr)
                sys.exit(1)
            show_ir(args[1])
            return

        if command == 'js':
            if len(args) < 2:
                print("Usage: python main.py js <file.epl>", file=sys.stderr)
                sys.exit(1)
            transpile_js(args[1])
            return

        if command == 'node':
            if len(args) < 2:
                print("Usage: python main.py node <file.epl>", file=sys.stderr)
                sys.exit(1)
            transpile_node(args[1])
            return

        if command == 'kotlin':
            if len(args) < 2:
                print("Usage: python main.py kotlin <file.epl>", file=sys.stderr)
                sys.exit(1)
            transpile_kotlin(args[1])
            return

        if command == 'python':
            if len(args) < 2:
                print("Usage: python main.py python <file.epl>", file=sys.stderr)
                sys.exit(1)
            transpile_python(args[1])
            return

        if command == 'android':
            if len(args) < 2:
                print("Usage: python main.py android <file.epl>", file=sys.stderr)
                sys.exit(1)
            use_compose = '--compose' in args
            generate_android(args[1], use_compose=use_compose)
            return

        if command == 'desktop':
            if len(args) < 2:
                print("Usage: python main.py desktop <file.epl> [--name AppName] [--width N] [--height N]", file=sys.stderr)
                sys.exit(1)
            app_name = None
            width, height = 900, 700
            i = 2
            while i < len(args):
                if args[i] == '--name' and i + 1 < len(args):
                    app_name = args[i + 1]; i += 2
                elif args[i] == '--width' and i + 1 < len(args):
                    width = int(args[i + 1]); i += 2
                elif args[i] == '--height' and i + 1 < len(args):
                    height = int(args[i + 1]); i += 2
                else:
                    i += 1
            generate_desktop(args[1], app_name=app_name, width=width, height=height)
            return

        if command == 'web':
            if len(args) < 2:
                print("Usage: python main.py web <file.epl> [--mode js|wasm|kotlin_js] [--name AppName]", file=sys.stderr)
                sys.exit(1)
            mode = 'js'
            app_name = None
            i = 2
            while i < len(args):
                if args[i] == '--mode' and i + 1 < len(args):
                    mode = args[i + 1]; i += 2
                elif args[i] == '--name' and i + 1 < len(args):
                    app_name = args[i + 1]; i += 2
                else:
                    i += 1
            generate_web(args[1], mode=mode, app_name=app_name)
            return

        if command == 'gui':
            if len(args) < 2:
                print("Usage: python main.py gui <file.epl>", file=sys.stderr)
                sys.exit(1)
            run_gui(args[1])
            return

        if command == 'playground':
            from epl.playground import start_playground
            port = 8080
            for i, a in enumerate(args):
                if a == '--port' and i + 1 < len(args):
                    port = int(args[i + 1])
            start_playground(port=port)
            return

        if command == 'notebook':
            from epl.notebook import start_notebook
            port = 8888
            for i, a in enumerate(args):
                if a == '--port' and i + 1 < len(args):
                    port = int(args[i + 1])
            start_notebook(port=port)
            return

        if command == 'blocks':
            from epl.block_editor import start_block_editor
            port = 8090
            for i, a in enumerate(args):
                if a == '--port' and i + 1 < len(args):
                    port = int(args[i + 1])
            start_block_editor(port=port)
            return

        if command == 'copilot':
            from epl.copilot import generate_from_description, run_copilot_interactive, start_copilot_web
            if '--web' in args:
                port = 8095
                for i, a in enumerate(args):
                    if a == '--port' and i + 1 < len(args):
                        port = int(args[i + 1])
                start_copilot_web(port=port)
            elif len(args) > 1 and args[1] != '--web':
                desc = ' '.join(args[1:])
                code = generate_from_description(desc)
                print(code)
            else:
                run_copilot_interactive()
            return

        if command == 'init':
            from epl.package_manager import init_project
            name = args[1] if len(args) > 1 else None
            init_project(name)
            return

        if command == 'install':
            if len(args) < 2:
                from epl.package_manager import install_dependencies
                install_dependencies()
            else:
                from epl.package_manager import install_package
                pkg_arg = args[1]
                local = '--local' in args
                no_save = '--no-save' in args
                install_package(pkg_arg, save=not no_save, local=local)
            return

        if command == 'gitinstall':
            if len(args) < 2:
                print("Usage: python main.py gitinstall <owner/repo> [alias]", file=sys.stderr)
                sys.exit(1)
            from epl.package_manager import add_github_dependency
            repo = args[1]
            alias = args[2] if len(args) > 2 and not args[2].startswith('--') else None
            no_save = '--no-save' in args
            add_github_dependency(repo, alias=alias, save=not no_save)
            return

        if command == 'gitremove':
            if len(args) < 2:
                print("Usage: python main.py gitremove <name-or-owner/repo>", file=sys.stderr)
                sys.exit(1)
            from epl.package_manager import remove_github_dependency
            remove_github_dependency(args[1])
            return

        if command == 'gitdeps':
            from epl.package_manager import list_github_dependencies
            deps = list_github_dependencies()
            if deps:
                print(f"\n  Declared GitHub Dependencies ({len(deps)}):")
                print("  " + "-" * 40)
                for alias, repo in deps:
                    print(f"  {alias:20s} -> {repo}")
            else:
                print("  No GitHub dependencies declared.")
            return

        if command == 'pyinstall':
            from epl.package_manager import install_python_dependencies, install_python_package
            if len(args) < 2:
                install_python_dependencies()
            else:
                import_name = args[1]
                requirement = args[2] if len(args) > 2 and not args[2].startswith('--') else None
                no_save = '--no-save' in args
                install_python_package(import_name, requirement, save=not no_save)
            return

        if command == 'pyremove':
            if len(args) < 2:
                print("Usage: python main.py pyremove <import-name>", file=sys.stderr)
                sys.exit(1)
            from epl.package_manager import remove_python_dependency
            remove_python_dependency(args[1])
            return

        if command == 'pydeps':
            from epl.package_manager import list_python_dependencies
            deps = list_python_dependencies()
            if deps:
                print(f"\n  Declared Python Dependencies ({len(deps)}):")
                print("  " + "-" * 40)
                for import_name, requirement in deps:
                    display = import_name if requirement in ('', '*') else requirement
                    print(f"  {import_name:20s} -> {display}")
            else:
                print("  No Python dependencies declared.")
            return

        if command == 'github':
            if len(args) < 2:
                print("Usage: python main.py github <clone|pull|push> ...", file=sys.stderr)
                sys.exit(1)
            from epl.github_tools import clone_repo, pull_repo, push_repo
            subcommand = args[1]
            if subcommand == 'clone':
                if len(args) < 3:
                    print("Usage: python main.py github clone <owner/repo> [dir]", file=sys.stderr)
                    sys.exit(1)
                repo = args[2]
                dest = args[3] if len(args) > 3 and not args[3].startswith('--') else None
                clone_repo(repo, dest=dest)
                return
            if subcommand == 'pull':
                pull_repo(args[2] if len(args) > 2 else '.')
                return
            if subcommand == 'push':
                path = '.'
                message = 'Update via EPL'
                remote = 'origin'
                branch = None
                i = 2
                if i < len(args) and not args[i].startswith('-'):
                    path = args[i]
                    i += 1
                while i < len(args):
                    if args[i] in ('-m', '--message') and i + 1 < len(args):
                        message = args[i + 1]
                        i += 2
                    elif args[i] == '--remote' and i + 1 < len(args):
                        remote = args[i + 1]
                        i += 2
                    elif args[i] == '--branch' and i + 1 < len(args):
                        branch = args[i + 1]
                        i += 2
                    else:
                        print(f"Unknown github push option: {args[i]}", file=sys.stderr)
                        sys.exit(1)
                push_repo(path=path, message=message, remote=remote, branch=branch)
                return
            print(f"Unknown github subcommand: {subcommand}", file=sys.stderr)
            sys.exit(1)

        if command == 'uninstall':
            if len(args) < 2:
                print("Usage: python main.py uninstall <package>", file=sys.stderr)
                sys.exit(1)
            from epl.package_manager import uninstall_package
            uninstall_package(args[1])
            return

        if command == 'packages':
            from epl.package_manager import list_packages
            pkgs = list_packages()
            if pkgs:
                print(f"\n  Installed EPL Packages ({len(pkgs)}):")
                print("  " + "-" * 40)
                for name, version, desc in pkgs:
                    print(f"  {name} @ {version}  {desc}")
            else:
                print("  No packages installed.")
            return

        if command == 'search':
            if len(args) < 2:
                print("Usage: python main.py search <query>", file=sys.stderr)
                sys.exit(1)
            from epl.registry import registry_search
            registry_search(' '.join(args[1:]))
            return

        if command == 'publish':
            from epl.registry import registry_publish
            repo = None
            path = '.'
            for i, a in enumerate(args[1:], 1):
                if a == '--repo' and i + 1 < len(args):
                    repo = args[i + 1]
                elif not a.startswith('--'):
                    path = a
            registry_publish(path, repo=repo)
            return

        if command == 'info':
            if len(args) < 2:
                print("Usage: python main.py info <package-name>", file=sys.stderr)
                sys.exit(1)
            from epl.registry import registry_info
            registry_info(args[1])
            return

        if command == 'stats':
            from epl.registry import registry_stats
            registry_stats()
            return

        if command == 'add':
            if len(args) < 2:
                print("Usage: epl add <package> [version]", file=sys.stderr)
                sys.exit(1)
            from epl.package_manager import add_dependency
            dev = '--dev' in args
            pkg_args = [a for a in args[1:] if not a.startswith('--')]
            name = pkg_args[0]
            ver = pkg_args[1] if len(pkg_args) > 1 else '*'
            add_dependency(name, ver, dev=dev)
            return

        if command == 'remove':
            if len(args) < 2:
                print("Usage: epl remove <package>", file=sys.stderr)
                sys.exit(1)
            from epl.package_manager import remove_dependency
            remove_dependency(args[1])
            return

        if command == 'lock':
            from epl.package_manager import create_lockfile
            create_lockfile()
            print("  Lockfile (epl.lock) generated.")
            return

        if command == 'update':
            if len(args) > 1:
                from epl.package_manager import update_package
                update_package(args[1])
            else:
                from epl.package_manager import update_all
                update_all()
            return

        if command == 'tree':
            from epl.package_manager import print_dependency_tree
            print_dependency_tree()
            return

        if command == 'outdated':
            from epl.package_manager import print_outdated
            print_outdated()
            return

        if command == 'audit':
            from epl.package_manager import print_audit
            print_audit()
            return

        if command == 'migrate':
            from epl.package_manager import migrate_manifest_to_toml
            if migrate_manifest_to_toml():
                print("  Migration complete. You can now delete epl.json.")
            else:
                print("  Nothing to migrate (already using epl.toml or no epl.json found).")
            return

        if command == 'cache':
            sub = args[1] if len(args) > 1 else 'info'
            if sub == 'clean':
                from epl.package_manager import clean_cache
                clean_cache()
            else:
                from epl.package_manager import CACHE_DIR
                import glob
                files = glob.glob(os.path.join(CACHE_DIR, '*')) if os.path.isdir(CACHE_DIR) else []
                total = sum(os.path.getsize(f) for f in files if os.path.isfile(f))
                print(f"  Cache: {len(files)} files, {total / 1024:.1f} KB")
                print(f"  Path: {CACHE_DIR}")
                print(f"  Clean: epl cache clean")
            return

        if command == 'site':
            from epl.site_generator import generate_site
            source_dirs = args[1:] if len(args) > 1 else None
            out_dir = None
            # Check for --output flag
            if source_dirs and '--output' in source_dirs:
                idx = source_dirs.index('--output')
                if idx + 1 < len(source_dirs):
                    out_dir = source_dirs[idx + 1]
                    source_dirs = source_dirs[:idx] + source_dirs[idx+2:]
            if not source_dirs:
                source_dirs = None
            out, count = generate_site(source_dirs, out_dir)
            print(f"Generated {count} pages in {out}/")
            return

        if command == 'ai':
            prompt = ' '.join(args[1:]) if len(args) > 1 else None
            run_ai_assistant(prompt)
            return

        if command == 'gen':
            desc = ' '.join(args[1:]) if len(args) > 1 else None
            run_gen(desc)
            return

        if command == 'explain':
            if len(args) < 2:
                print("Usage: python main.py explain <file.epl>", file=sys.stderr)
                sys.exit(1)
            run_explain(args[1])
            return

        if command == 'cloud':
            run_cloud_setup()
            return

        if command == 'train':
            run_train_model()
            return

        if command == 'model':
            run_model_manager()
            return

        if command == 'debug':
            if len(args) < 2:
                print("Usage: python main.py debug <file.epl> [-b <line>]", file=sys.stderr)
                sys.exit(1)
            run_debugger(args[1], args[2:])
            return

        if command == 'test':
            targets = args[1:] if len(args) > 1 else ['.']
            run_test_framework(targets)
            return

        if command == 'lint':
            targets = args[1:] if len(args) > 1 else ['.']
            run_linter(targets)
            return

        if command == 'docs':
            targets = args[1:] if len(args) > 1 else ['.']
            run_doc_generator(targets)
            return

        if command == 'fmt':
            if len(args) < 2:
                print("Usage: python main.py fmt <file.epl> [--check] [--in-place]", file=sys.stderr)
                sys.exit(1)
            run_formatter(args[1:])
            return

        if command == 'deploy':
            from epl.deploy import deploy_cli
            deploy_cli(args[1:])
            return

        if command == 'serve':
            if len(args) < 2:
                print("Usage: python main.py serve <file.epl> [--port N] [--workers N] [--reload] [--store memory|sqlite|redis] [--session memory|sqlite|redis]", file=sys.stderr)
                sys.exit(1)
            _run_serve_command(args[1:])
            return

        if command == 'lsp':
            run_lsp_server()
            return

        if command == 'vm':
            if len(args) < 2:
                print("Usage: python main.py vm <file.epl>", file=sys.stderr)
                sys.exit(1)
            run_vm(args[1])
            return

        if command == 'package':
            if len(args) < 2:
                print("Usage: python main.py package <file.epl> [--mode exe|zip|native]", file=sys.stderr)
                sys.exit(1)
            run_packager(args[1], args[2:])
            return

        if command == 'build':
            if len(args) < 2:
                print("Usage: python main.py build <file.epl> [--opt 0|1|2|3] [--static] [--target <target>]", file=sys.stderr)
                print("  Builds a standalone native executable (no Python needed).", file=sys.stderr)
                print("  Targets: " + ", ".join(sorted(CROSS_TARGETS.keys())), file=sys.stderr)
                sys.exit(1)
            opt_level = 2
            static_link = True  # build defaults to static for standalone
            target = None
            i = 2
            while i < len(args):
                if args[i] == '--opt' and i + 1 < len(args):
                    opt_level = int(args[i + 1])
                    i += 2
                elif args[i] == '--static':
                    static_link = True
                    i += 1
                elif args[i] == '--no-static':
                    static_link = False
                    i += 1
                elif args[i] == '--target' and i + 1 < len(args):
                    target = args[i + 1]
                    i += 2
                else:
                    i += 1
            return 0 if compile_file(args[1], opt_level=opt_level, static=static_link, target=target) else 1

        if command == 'micropython':
            if len(args) < 2:
                print("Usage: python main.py micropython <file.epl> [--target esp32|pico]", file=sys.stderr)
                sys.exit(1)
            target = 'esp32'
            valid_targets = ('esp32', 'pico')
            for i, a in enumerate(args):
                if a == '--target' and i + 1 < len(args):
                    target = args[i + 1]
            if target not in valid_targets:
                print(f"Error: Unknown target '{target}'. Valid: {', '.join(valid_targets)}", file=sys.stderr)
                sys.exit(1)
            transpile_micropython(args[1], target)
            return

        if command == 'wasm':
            if len(args) < 2:
                print("Usage: python main.py wasm <file.epl>", file=sys.stderr)
                sys.exit(1)
            _compile_to_wasm(args[1])
            return

        if command == 'benchmark':
            if len(args) < 2:
                print("Usage: python main.py benchmark <file.epl>", file=sys.stderr)
                sys.exit(1)
            run_benchmark(args[1])
            return

        if command == 'profile':
            if len(args) < 2:
                print("Usage: python main.py profile <file.epl> [--trace <out.json>] [--top N]", file=sys.stderr)
                sys.exit(1)
            run_profiler(args[1], args[2:])
            return

        if command == 'bench':
            from benchmarks.run_benchmarks import run_suite
            bench_json = '--json' in args
            bench_runs = 5
            for a in args[1:]:
                if a.startswith('--runs='):
                    bench_runs = int(a.split('=')[1])
            run_suite(runs=bench_runs, json_output=bench_json)
            return

        # Phase 7: resolve command
        if command == 'resolve':
            from epl.resolver import resolve_from_manifest, print_resolution
            result = resolve_from_manifest()
            print_resolution(result)
            return

        # Phase 7: workspace command
        if command == 'workspace':
            from epl.workspace import workspace_cli
            workspace_cli(args[1:])
            return

        # Phase 7: ci command
        if command == 'ci':
            from epl.ci_gen import ci_cli
            ci_cli(args[1:])
            return

        # Phase 7: sync-index command
        if command == 'sync-index':
            from epl.package_index import PackageIndex
            idx = PackageIndex()
            if idx.sync_index(force='--force' in args):
                print("  Package index synced successfully.")
            else:
                print("  Failed to sync package index.")
            return

        # Default: treat as file to run (VM default, fallback to interpreter)
        run_file(command, strict=strict, safe_mode=sandbox, force_interpret=force_interpret, json_errors=json_errors)
    else:
        run_repl()


def main(argv=None):
    """Authoritative source-checkout entry point backed by epl.cli."""
    from epl.cli import cli_main
    return cli_main(argv)


def run_gui(filepath):
    """Run an EPL file with GUI support."""
    source = _read_source(filepath)
    try:
        from epl.gui import gui_available, EPLWindow
        if not gui_available():
            print("EPL Error: GUI requires tkinter. Install it and try again.", file=sys.stderr)
            sys.exit(1)
        interpreter = Interpreter()
        # Inject gui module into interpreter environment
        interpreter.environment.set('EPLWindow', EPLWindow)
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        interpreter.execute(program)
    except EPLError as e:
        print(f"\n{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"EPL Error: {e}", file=sys.stderr)
        sys.exit(1)


def transpile_js(filepath):
    """Transpile EPL to JavaScript."""
    source = _read_source(filepath)
    try:
        from epl.js_transpiler import transpile_to_js
        program = _parse_source(source)
        js = transpile_to_js(program)
        out = os.path.splitext(os.path.basename(filepath))[0] + '.js'
        with open(out, 'w', encoding='utf-8') as f:
            f.write(js)
        print(f"  JavaScript written to: {out}")
    except Exception as e:
        print(f"EPL Error: {e}", file=sys.stderr)
        sys.exit(1)


def transpile_node(filepath):
    """Transpile EPL to Node.js."""
    source = _read_source(filepath)
    try:
        from epl.js_transpiler import transpile_to_node
        program = _parse_source(source)
        js = transpile_to_node(program)
        out = os.path.splitext(os.path.basename(filepath))[0] + '.node.js'
        with open(out, 'w', encoding='utf-8') as f:
            f.write(js)
        print(f"  Node.js written to: {out}")
    except Exception as e:
        print(f"EPL Error: {e}", file=sys.stderr)
        sys.exit(1)


def transpile_kotlin(filepath):
    """Transpile EPL to Kotlin."""
    source = _read_source(filepath)
    try:
        from epl.kotlin_gen import transpile_to_kotlin
        program = _parse_source(source)
        kt = transpile_to_kotlin(program)
        out = os.path.splitext(os.path.basename(filepath))[0] + '.kt'
        with open(out, 'w', encoding='utf-8') as f:
            f.write(kt)
        print(f"  Kotlin written to: {out}")
    except Exception as e:
        print(f"EPL Error: {e}", file=sys.stderr)
        sys.exit(1)


def transpile_python(filepath):
    """Transpile EPL to Python."""
    source = _read_source(filepath)
    try:
        from epl.python_transpiler import transpile_to_python
        program = _parse_source(source)
        py = transpile_to_python(program)
        out = os.path.splitext(os.path.basename(filepath))[0] + '.py'
        with open(out, 'w', encoding='utf-8') as f:
            f.write(py)
        print(f"  Python written to: {out}")
    except Exception as e:
        print(f"EPL Error: {e}", file=sys.stderr)
        sys.exit(1)


def generate_android(filepath, use_compose=False):
    """Generate an Android project from EPL."""
    source = _read_source(filepath)
    try:
        from epl.kotlin_gen import generate_android_project
        program = _parse_source(source)
        base = os.path.splitext(os.path.basename(filepath))[0]
        out_dir = f'{base}_android'
        generate_android_project(program, out_dir, app_name=base.title())
        print(f"  Android project generated: {out_dir}/")
        if use_compose:
            print(f"  Mode: Jetpack Compose")
        print(f"  Open in Android Studio to build.")
    except Exception as e:
        print(f"EPL Error: {e}", file=sys.stderr)
        sys.exit(1)


def generate_desktop(filepath, app_name=None, width=900, height=700):
    """Generate a Compose Multiplatform Desktop project from EPL."""
    source = _read_source(filepath)
    try:
        from epl.desktop import generate_desktop_project
        program = _parse_source(source)
        base = os.path.splitext(os.path.basename(filepath))[0]
        name = app_name or base.title().replace('_', '')
        out_dir = f'{base}_desktop'
        generate_desktop_project(program, out_dir, app_name=name,
                                  width=width, height=height)
        print(f"  Desktop project generated: {out_dir}/")
        print(f"  App: {name} ({width}x{height})")
        print(f"  Build: cd {out_dir} && ./gradlew run")
        print(f"  Package: ./gradlew packageMsi  (or packageDmg/packageDeb)")
    except Exception as e:
        print(f"EPL Error: {e}", file=sys.stderr)
        sys.exit(1)


def generate_web(filepath, mode='js', app_name=None):
    """Generate a browser-ready web project from EPL."""
    source = _read_source(filepath)
    try:
        from epl.wasm_web import generate_web_project
        program = _parse_source(source)
        base = os.path.splitext(os.path.basename(filepath))[0]
        name = app_name or base.title().replace('_', '')
        out_dir = f'{base}_web'
        generate_web_project(program, out_dir, app_name=name, mode=mode)
        print(f"  Web project generated: {out_dir}/")
        print(f"  Mode: {mode}")
        if mode == 'js':
            print(f"  Run: python -m http.server 3000 --directory {out_dir}/public")
        elif mode == 'wasm':
            print(f"  Build: cd {out_dir} && ./build.sh")
            print(f"  Run: python -m http.server 3000 --directory {out_dir}/public")
        elif mode == 'kotlin_js':
            print(f"  Build: cd {out_dir} && ./gradlew jsBrowserDevelopmentRun")
    except Exception as e:
        print(f"EPL Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_ai_assistant(initial_prompt=None):
    """Run the AI code assistant. Uses Groq cloud if configured, else Ollama."""
    try:
        from epl.ai import (code_assist, is_available, Conversation,
                             ensure_epl_model, EPL_MODEL_NAME,
                             _use_cloud, get_cloud_status)
        
        using_cloud = _use_cloud()
        
        if not using_cloud:
            if not is_available():
                print("  Ollama is not running. Start it with: ollama serve")
                print("  Or use Groq cloud (free, instant): python main.py cloud --setup")
                return
            ensure_epl_model(verbose=False)
        
        if initial_prompt:
            result = code_assist(initial_prompt)
            print(result)
            return
        
        # Show provider info
        if using_cloud:
            status = get_cloud_status()
            provider = status.get('provider', 'cloud').title()
            model = status.get('model', 'auto')
            print(f"  EPL AI Assistant [\u2601 {provider}: {model}]")
            print(f"  Tip: 'python main.py cloud --off' to switch to local Ollama.")
        else:
            model_name = EPL_MODEL_NAME if is_available() else 'default'
            print(f"  EPL AI Assistant [local: {model_name}]")
            print(f"  Tip: 'python main.py cloud --setup' for instant cloud AI.")
        
        print("  Type your questions or 'quit' to exit.\n")
        conv = Conversation(system="You are EPL-Coder, an expert EPL programming assistant.")
        while True:
            try:
                q = input("AI> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break
            if q.lower() in ('quit', 'exit', 'q'):
                break
            if q:
                print(conv.say(q))
                print()
    except Exception as e:
        print(f"AI Error: {e}", file=sys.stderr)


def run_cloud_setup():
    """Configure cloud AI provider (Gemini or Groq)."""
    try:
        from epl.ai import (configure_cloud, clear_cloud, get_cloud_status,
                             GROQ_MODELS, GEMINI_MODELS, _use_cloud)

        args = sys.argv[2:]

        # Help
        if not args or '--help' in args or '-h' in args:
            status = get_cloud_status()
            print("\n  ╔══════════════════════════════════════╗")
            print("  ║     Cloud AI Configuration            ║")
            print("  ╚══════════════════════════════════════╝")
            if status.get('active'):
                print(f"\n  ✓ Active: {status['provider'].title()} ({status['model']})")
                print(f"  Key:     {status['key_masked']}")
            else:
                print(f"\n  Status: Not configured (using local Ollama)")
            print("\n  Providers:")
            print("  Gemini  — Google, free, works globally   https://aistudio.google.com/apikey")
            print("  Groq    — Fast, free (may be region-locked) https://console.groq.com/keys")
            print("\n  Commands:")
            print("  python main.py cloud --setup             Interactive setup")
            print("  python main.py cloud --gemini <key>      Set Google Gemini key")
            print("  python main.py cloud --groq <key>        Set Groq API key")
            print("  python main.py cloud --model <model>     Change cloud model")
            print("  python main.py cloud --models            List available models")
            print("  python main.py cloud --status            Show current config")
            print("  python main.py cloud --off               Disable cloud, use Ollama")
            return

        # --off: disable cloud
        if '--off' in args:
            clear_cloud()
            print("  Cloud AI disabled. Using local Ollama.")
            return

        # --status
        if '--status' in args:
            status = get_cloud_status()
            if status.get('active'):
                print(f"\n  Provider: {status['provider'].title()}")
                print(f"  Model:    {status['model']}")
                print(f"  Key:      {status['key_masked']}")
                print(f"  Status:   ✓ Active")
            else:
                print("\n  Cloud AI not configured.")
                print("  Run: python main.py cloud --setup")
            return

        # --models
        if '--models' in args:
            print("\n  Available Gemini Models (free, recommended):")
            print("  " + "-" * 60)
            for name, desc in GEMINI_MODELS:
                print(f"  {name:<30} {desc}")
            print("\n  Available Groq Models (free, may be region-locked):")
            print("  " + "-" * 60)
            for name, desc in GROQ_MODELS:
                print(f"  {name:<30} {desc}")
            return

        # --gemini <key>: set Gemini key
        if '--gemini' in args:
            idx = args.index('--gemini')
            if idx + 1 >= len(args):
                print("  Usage: python main.py cloud --gemini <your_api_key>")
                print("  Get key: https://aistudio.google.com/apikey")
                return
            key = args[idx + 1]
            model = None
            if '--model' in args:
                midx = args.index('--model')
                if midx + 1 < len(args):
                    model = args[midx + 1]
            configure_cloud('gemini', key, model)
            masked = key[:8] + '...' + key[-4:]
            print(f"\n  ✓ Google Gemini configured!")
            print(f"  Key:   {masked}")
            print(f"  Model: {model or 'gemini-2.0-flash (auto)'}")
            print(f"\n  Test it: python main.py ai \"Write hello world in EPL\"")
            return

        # --groq <key>: set Groq key
        if '--groq' in args:
            idx = args.index('--groq')
            if idx + 1 >= len(args):
                print("  Usage: python main.py cloud --groq <your_api_key>")
                return
            key = args[idx + 1]
            model = None
            if '--model' in args:
                midx = args.index('--model')
                if midx + 1 < len(args):
                    model = args[midx + 1]
            configure_cloud('groq', key, model)
            masked = key[:8] + '...' + key[-4:]
            print(f"\n  ✓ Groq API configured!")
            print(f"  Key:   {masked}")
            print(f"  Model: {model or 'llama-3.3-70b-versatile (auto)'}")
            print(f"\n  Test it: python main.py ai \"Write hello world in EPL\"")
            return

        # --key <key>: legacy, auto-detect provider
        if '--key' in args:
            idx = args.index('--key')
            if idx + 1 >= len(args):
                print("  Usage: python main.py cloud --gemini <key>  or  --groq <key>")
                return
            key = args[idx + 1]
            provider = 'groq' if key.startswith('gsk_') else 'gemini'
            model = None
            if '--model' in args:
                midx = args.index('--model')
                if midx + 1 < len(args):
                    model = args[midx + 1]
            configure_cloud(provider, key, model)
            masked = key[:8] + '...' + key[-4:]
            print(f"\n  ✓ {provider.title()} configured!")
            print(f"  Key:   {masked}")
            print(f"\n  Test it: python main.py ai \"Write hello world in EPL\"")
            return

        # --model <model>: change model (requires existing config)
        if '--model' in args:
            idx = args.index('--model')
            if idx + 1 >= len(args):
                print("  Usage: python main.py cloud --model <model_name>")
                return
            status = get_cloud_status()
            if not status.get('active'):
                print("  No cloud provider configured. Run: python main.py cloud --setup")
                return
            from epl.ai import CLOUD_API_KEY, CLOUD_PROVIDER
            model = args[idx + 1]
            configure_cloud(CLOUD_PROVIDER, CLOUD_API_KEY, model)
            print(f"  ✓ Cloud model changed to: {model}")
            return

        # --setup: interactive
        if '--setup' in args:
            print("\n  Cloud AI Setup")
            print("  " + "-" * 50)
            print("  Choose a provider:\n")
            print("  [1] Google Gemini  — Free, fast, works globally (recommended)")
            print("  [2] Groq           — Free, very fast (may be region-locked)\n")
            try:
                choice = input("  Provider (1/2): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Cancelled.")
                return
            if choice == '2':
                provider = 'groq'
                print("\n  Get a free Groq key: https://console.groq.com/keys")
            else:
                provider = 'gemini'
                print("\n  Get a free Gemini key: https://aistudio.google.com/apikey")
            try:
                key = input("  API Key: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Cancelled.")
                return
            if not key:
                print("  No key provided. Cancelled.")
                return
            configure_cloud(provider, key)
            masked = key[:8] + '...' + key[-4:]
            print(f"\n  ✓ {provider.title()} configured! Key: {masked}")
            print(f"  Test it: python main.py ai \"Write hello world in EPL\"")
            return

        # Fallback: treat first arg as API key, auto-detect provider
        key = args[0]
        if key.startswith('gsk_') or key.startswith('AIza') or len(key) > 20:
            provider = 'groq' if key.startswith('gsk_') else 'gemini'
            configure_cloud(provider, key)
            masked = key[:8] + '...' + key[-4:]
            print(f"\n  ✓ {provider.title()} configured!")
            print(f"  Key:   {masked}")
            print(f"\n  Test it: python main.py ai \"Write hello world in EPL\"")
        else:
            print(f"  Unknown option: {key}")
            print("  Run: python main.py cloud --help")

    except Exception as e:
        print(f"  Cloud Error: {e}", file=sys.stderr)


def run_train_model():
    """Train/create the custom EPL-Coder model in Ollama."""
    try:
        from epl.ai import (
            is_available, create_epl_model, model_exists,
            delete_epl_model, list_base_models, EPL_MODEL_NAME
        )

        # Handle offline-safe flags first (no Ollama needed)
        args = sys.argv[2:]
        for arg in args:
            if arg in ('--help', '-h'):
                print("\n  EPL Model Training")
                print("  " + "-" * 40)
                print("  python main.py train                Create EPL-Coder model")
                print("  python main.py train --base <model> Use specific base model")
                print("  python main.py train --force        Recreate even if exists")
                print("  python main.py train --delete       Remove EPL-Coder model")
                print("  python main.py train --list         Show base model options")
                return
            if arg in ('--list', '--models'):
                print("\n  Recommended base models for EPL:")
                print("  " + "-" * 55)
                for name, size, desc in list_base_models():
                    print(f"  {name:<20} {size:<10} {desc}")
                print(f"\n  Usage: python main.py train --base <model>")
                return

        # Ollama required for remaining operations
        if not is_available():
            print("\n  Ollama is not running. Start it with: ollama serve")
            print("  Install from: https://ollama.com")
            return

        # Parse options
        base_model = None
        force = False
        for i, arg in enumerate(sys.argv[2:], 2):
            if arg == '--base' and i + 1 < len(sys.argv):
                base_model = sys.argv[i + 1]
            elif arg == '--force':
                force = True
            elif arg == '--delete':
                delete_epl_model()
                return

        if model_exists() and not force:
            print(f"\n  EPL model '{EPL_MODEL_NAME}' already exists!")
            print(f"  Use --force to recreate, or --delete to remove.")
            print(f"  Or just run: python main.py ai")
            return

        print()
        print("  ╔══════════════════════════════════════╗")
        print("  ║     EPL-Coder Model Training         ║")
        print("  ╚══════════════════════════════════════╝")
        print()

        if model_exists() and force:
            print("  Removing existing model...")
            delete_epl_model(verbose=False)

        ok = create_epl_model(base_model=base_model)
        if ok:
            print("\n  Training complete! The model has learned:")
            print("    - Full EPL syntax reference")
            print("    - 15+ conversation examples")
            print("    - Code patterns and best practices")
            print("    - String, list, map, class, enum operations")
            print("    - Error handling and functional programming")
    except Exception as e:
        print(f"  Training Error: {e}", file=sys.stderr)


def run_model_manager():
    """Manage AI models."""
    try:
        from epl.ai import (
            is_available, list_models, model_exists, get_model_info,
            EPL_MODEL_NAME, list_base_models
        )

        sub = sys.argv[2] if len(sys.argv) > 2 else 'list'

        # Offline-safe subcommands
        if sub == 'bases':
            print("\n  Recommended Base Models:")
            print("  " + "-" * 55)
            for name, size, desc in list_base_models():
                print(f"  {name:<20} {size:<10} {desc}")
            return

        if sub in ('--help', '-h', 'help'):
            print("\n  Model Management:")
            print("  python main.py model list     List installed models")
            print("  python main.py model info     Show EPL model details")
            print("  python main.py model bases    Show base model options")
            return

        # Requires Ollama for remaining subcommands
        if not is_available():
            print("\n  Ollama is not running.")
            return

        if sub == 'list':
            models = list_models()
            epl_exists = model_exists()
            print("\n  Installed Ollama Models:")
            print("  " + "-" * 40)
            if not models:
                print("  (none)")
            for m in models:
                tag = " ← EPL-Coder" if EPL_MODEL_NAME in m else ""
                print(f"  {m}{tag}")
            print()
            if not epl_exists:
                print("  EPL model not installed. Run: python main.py train")
            return

        if sub == 'info':
            info = get_model_info()
            if info:
                params = info.get('details', {}).get('parameter_size', 'N/A')
                family = info.get('details', {}).get('family', 'N/A')
                fmt = info.get('details', {}).get('format', 'N/A')
                print(f"\n  Model: {EPL_MODEL_NAME}")
                print(f"  Family: {family}")
                print(f"  Parameters: {params}")
                print(f"  Format: {fmt}")
            else:
                print(f"  Model '{EPL_MODEL_NAME}' not found. Run: python main.py train")
            return

        print(f"\n  Unknown subcommand: {sub}")
        print("  Try: python main.py model --help")
    except Exception as e:
        print(f"  Model Error: {e}", file=sys.stderr)


def run_gen(description=None):
    """Generate EPL code from a natural language description."""
    try:
        from epl.ai import is_available, generate_epl_code, ensure_epl_model
        if not description:
            print("Usage: python main.py gen <description>", file=sys.stderr)
            print('Example: python main.py gen "sort a list of numbers"', file=sys.stderr)
            return

        if not is_available():
            print("  Ollama is not running. Start it with: ollama serve")
            return

        ensure_epl_model(verbose=False)

        # Determine output filename
        safe_name = description[:30].replace(' ', '_').replace('"', '').replace("'", '')
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '_')
        filename = f"{safe_name}.epl"

        print(f"\n  Generating EPL code: \"{description}\"")
        print(f"  ────────────────────────────────────────────")

        code, full_response = generate_epl_code(description, filename=filename)

        if code:
            print(f"\n{full_response}")
            print(f"\n  ────────────────────────────────────────────")
            print(f"  Saved to: {filename}")
            print(f"  Run it:   python main.py {filename}")
        else:
            print("  Could not generate code. Try a more specific description.")

    except Exception as e:
        print(f"  Gen Error: {e}", file=sys.stderr)


def run_explain(filepath):
    """Use AI to explain what an EPL file does."""
    try:
        from epl.ai import is_available, explain_code, ensure_epl_model
        source = _read_source(filepath)

        if not is_available():
            print("  Ollama is not running. Start it with: ollama serve")
            return

        ensure_epl_model(verbose=False)

        print(f"\n  Analyzing: {filepath}")
        print(f"  ────────────────────────────────────────────")
        explanation = explain_code(source)
        print(f"\n{explanation}")

    except Exception as e:
        print(f"  Explain Error: {e}", file=sys.stderr)


def run_debugger(filepath, extra_args):
    """Run the EPL debugger on a file."""
    source = _read_source(filepath)
    try:
        from epl.debugger import EPLDebugger, DebugInterpreter

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

        print(f"  EPL Debugger — {filepath}")
        print(f"  Breakpoints: {len(debugger.breakpoints)}")
        print(f"  Type 'help' for commands, 'c' to continue\n")
        interp.execute(program)

    except EPLError as e:
        print(f"\n{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Debugger Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_test_framework(targets):
    """Run EPL tests using the test framework."""
    try:
        from epl.test_framework import EPLTestRunner

        runner = EPLTestRunner(verbose=True)
        total_passed = 0
        total_failed = 0

        for target in targets:
            if os.path.isdir(target):
                # Find all test_*.epl files
                for root, dirs, files in os.walk(target):
                    for f in sorted(files):
                        if f.startswith('test_') and f.endswith('.epl'):
                            fpath = os.path.join(root, f)
                            print(f"\n  Running: {fpath}")
                            result = runner.run_file(fpath)
                            total_passed += result.passed
                            total_failed += result.failed
            elif os.path.isfile(target) and target.endswith('.epl'):
                print(f"\n  Running: {target}")
                result = runner.run_file(target)
                total_passed += result.passed
                total_failed += result.failed
            else:
                print(f"  Skipping: {target} (not an .epl file or directory)")

        print(f"\n  {'=' * 50}")
        print(f"  Total: {total_passed + total_failed} tests, {total_passed} passed, {total_failed} failed")
        if total_failed > 0:
            sys.exit(1)

    except Exception as e:
        print(f"Test Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_linter(targets):
    """Lint EPL source files."""
    try:
        from epl.doc_linter import Linter, LintConfig

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
                print(f"  Not found: {target}")

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
            print(f"  Fixed {fix_total} issues")
        else:
            print(linter.format_report(all_issues))
            errors = sum(1 for i in all_issues if i.severity == 'error')
            if errors:
                sys.exit(1)

    except Exception as e:
        print(f"Lint Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_doc_generator(targets):
    """Generate documentation from EPL source files."""
    try:
        from epl.doc_linter import DocGenerator
        from pathlib import Path

        gen = DocGenerator()

        for target in targets:
            if os.path.isdir(target):
                gen.parse_directory(target)
            elif os.path.isfile(target):
                gen.parse_file(target)
            else:
                print(f"  Not found: {target}")

        if not gen.modules:
            print("  No EPL files found.")
            return

        out_dir = Path('docs')
        out_dir.mkdir(parents=True, exist_ok=True)

        (out_dir / 'api.md').write_text(gen.to_markdown(), encoding='utf-8')
        (out_dir / 'api.html').write_text(gen.to_html(), encoding='utf-8')
        (out_dir / 'api.json').write_text(gen.to_json(), encoding='utf-8')

        total_entries = sum(len(m.entries) for m in gen.modules)
        print(f"\n  Documentation generated:")
        print(f"    {len(gen.modules)} modules, {total_entries} documented items")
        print(f"    docs/api.html  — Searchable HTML documentation")
        print(f"    docs/api.md    — Markdown documentation")
        print(f"    docs/api.json  — Machine-readable JSON")

    except Exception as e:
        print(f"Docs Error: {e}", file=sys.stderr)
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
        print("Usage: python main.py fmt <file.epl> [--check] [--in-place]", file=sys.stderr)
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
            print(f"File not found: {filepath}", file=sys.stderr)
            continue
        with open(filepath, 'r', encoding='utf-8') as fh:
            original = fh.read()
        formatted = format_epl_source(original)
        if formatted != original:
            any_changed = True
            if check_only:
                print(f"  NEEDS FORMATTING: {filepath}")
            elif in_place:
                with open(filepath, 'w', encoding='utf-8') as fh:
                    fh.write(formatted)
                print(f"  FORMATTED: {filepath}")
            else:
                print(formatted)
        else:
            if not check_only:
                print(f"  OK: {filepath}")

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
            print(f"  EPL Language Server starting on TCP port {port}...")
            print(f"  Connect your IDE to localhost:{port}")
            server = EPLLanguageServer()
            server.start_tcp(port)
        else:
            # stdio mode (default for VS Code)
            server = EPLLanguageServer()
            server.start_stdio()

    except Exception as e:
        print(f"LSP Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_profiler(filepath, extra_args):
    """Profile an EPL file — shows per-function timing, call counts, and hotspots."""
    source = _read_source(filepath)
    import time as _time

    # Parse args
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

        print(f"  EPL Profiler — {os.path.basename(filepath)}")
        print()

        t0 = _time.perf_counter()

        # Run via interpreter with profiler hooks
        set_source_context(source, filepath)
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        interp = Interpreter()
        interp.execute(program)

        total_time = (_time.perf_counter() - t0) * 1000
        profiler.disable()

        # Print output
        for line in interp.output_lines:
            print(line)

        # Print profiler report
        print()
        print(profiler.report())
        print(f"\n  Wall time: {total_time:.2f} ms")

        stats = profiler.get_stats()
        if stats:
            # Hotspot analysis
            sorted_funcs = sorted(stats.items(), key=lambda x: x[1]['total_ms'], reverse=True)
            if len(sorted_funcs) > top_n:
                sorted_funcs = sorted_funcs[:top_n]
            print(f"\n  Top {min(top_n, len(sorted_funcs))} hotspots:")
            for name, s in sorted_funcs:
                pct = (s['total_ms'] / total_time * 100) if total_time > 0 else 0
                print(f"    {pct:5.1f}%  {s['total_ms']:8.2f}ms  {s['calls']:>4}x  {name}")

        # Export trace if requested
        if trace_file:
            profiler.export_trace(trace_file)
            print(f"\n  Trace exported to: {trace_file}")
            print(f"  View at: chrome://tracing")

    except EPLError as e:
        print(f"\n{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Profiler Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_vm(filepath):
    """Run an EPL file using the fast bytecode VM."""
    source = _read_source(filepath)
    try:
        from epl.vm import compile_and_run
        print(f"  EPL Bytecode VM — {os.path.basename(filepath)}")
        print()
        result = compile_and_run(source)
        if result.get('error'):
            print(f"\nVM Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        if result.get('output'):
            for line in result['output']:
                print(line)
    except EPLError as e:
        print(f"\n{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"VM Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_packager(filepath, extra_args):
    """Package an EPL file into a standalone distributable."""
    source_path = os.path.abspath(filepath)
    if not os.path.exists(source_path):
        print(f"EPL Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    try:
        from epl.packager import package

        # Parse extra args
        mode = 'exe'
        output_dir = None
        i = 0
        while i < len(extra_args):
            if extra_args[i] == '--mode' and i + 1 < len(extra_args):
                mode = extra_args[i + 1]
                i += 2
            elif extra_args[i] == '--output' and i + 1 < len(extra_args):
                output_dir = extra_args[i + 1]
                i += 2
            else:
                i += 1

        print(f"  EPL Packager — {os.path.basename(filepath)}")
        print(f"  Mode: {mode}")
        print()
        result = package(source_path, mode=mode, output_dir=output_dir)
        if result:
            print(f"\n  Package created: {result}")
        else:
            print("\n  Packaging complete.")

    except EPLError as e:
        print(f"\n{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Packager Error: {e}", file=sys.stderr)
        sys.exit(1)


def _read_source(filepath):
    """Read source file or exit with error."""
    if not os.path.exists(filepath):
        print(f"EPL Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def _parse_source(source):
    """Parse EPL source into AST."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def transpile_micropython(filepath, target='esp32'):
    """Transpile EPL to MicroPython for embedded/IoT targets."""
    source = _read_source(filepath)
    try:
        from epl.micropython_transpiler import transpile_to_micropython
        program = _parse_source(source)
        mpy = transpile_to_micropython(program, target=target)
        out = os.path.splitext(os.path.basename(filepath))[0] + f'_{target}_mpy.py'
        with open(out, 'w', encoding='utf-8') as f:
            f.write(mpy)
        print(f"  MicroPython written to: {out}")
        print(f"  Target: {target.upper()}")
        print(f"  Upload with: mpremote cp {out} :")
    except Exception as e:
        print(f"EPL Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_benchmark(filepath, runs=5, warmup=1):
    """Benchmark VM vs interpreter for an EPL file with warmup and statistics."""
    source = _read_source(filepath)
    import time as _time

    print(f"  EPL Benchmark — {os.path.basename(filepath)}")
    print(f"  Runs: {runs}, Warmup: {warmup}")
    print("  " + "=" * 50)

    # VM benchmark
    vm_time = None
    try:
        from epl.vm import compile_and_run
        # Warmup
        for _ in range(warmup):
            compile_and_run(source)
        # Timed runs
        times = []
        ips_total = 0
        for _ in range(runs):
            t0 = _time.perf_counter()
            result = compile_and_run(source)
            times.append(_time.perf_counter() - t0)
            ips_total += result.get('instructions_executed', 0)
        vm_time = min(times)
        avg_time = sum(times) / len(times)
        avg_ips = ips_total // runs
        print(f"  VM:          {vm_time:.4f}s best, {avg_time:.4f}s avg  ({avg_ips:,} instructions)")
    except Exception as e:
        print(f"  VM:          FAILED ({e})")

    # Interpreter benchmark
    interp_time = None
    try:
        set_source_context(source, filepath)
        # Warmup
        for _ in range(warmup):
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            Interpreter().execute(program)
        # Timed runs
        times = []
        for _ in range(runs):
            t0 = _time.perf_counter()
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            interp = Interpreter()
            interp.execute(program)
            times.append(_time.perf_counter() - t0)
        interp_time = min(times)
        avg_time = sum(times) / len(times)
        print(f"  Interpreter: {interp_time:.4f}s best, {avg_time:.4f}s avg")
    except Exception as e:
        print(f"  Interpreter: FAILED ({e})")

    if vm_time and interp_time:
        speedup = interp_time / vm_time if vm_time > 0 else float('inf')
        print(f"  Speedup:     {speedup:.1f}x (best of {runs})")
    print("  " + "=" * 50)


if __name__ == "__main__":
    sys.exit(main())
