"""
EPL - English Programming Language CLI (v7.0)
Standalone command-line interface for the EPL programming language.

This is the primary entry point for the `epl` command.
Usage:
    epl run <file.epl>           Run an EPL program
    epl new <name> [--template]  Create a new EPL project
    epl build <file.epl>         Compile to native executable
    epl wasm <file.epl>          Compile to WebAssembly
    epl test [dir|file]          Run tests
    epl repl                     Interactive REPL
    epl install [--frozen] [package] Install project deps or a package
    epl gitinstall <owner/repo>  Install/save a GitHub package dependency
    epl gitremove <name>         Remove a GitHub dependency declaration
    epl gitdeps                  List GitHub package dependencies
    epl pyinstall <import> [spec] Install/save a Python package
    epl pyremove <import>        Remove a Python package declaration
    epl pydeps                   List Python ecosystem dependencies
    epl github <cmd>             Clone/pull/push GitHub projects
    epl serve <file.epl>         Start production server
    epl desktop <file.epl>       Generate desktop app project
    epl web <file.epl>           Generate web app bundle
    epl <file.epl>               Shorthand for 'epl run'
    epl --version                Show version
    epl --help                   Show help
"""

import sys
import os

# Python version guard
if sys.version_info < (3, 9):
    print(f"EPL requires Python 3.9 or later (found {sys.version_info.major}.{sys.version_info.minor}).")
    print("Please upgrade Python: https://python.org/downloads/")
    sys.exit(1)

# Ensure EPL root is on the path
_EPL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EPL_ROOT not in sys.path:
    sys.path.insert(0, _EPL_ROOT)

from epl import __version__

# ─── ANSI Colors ──────────────────────────────────────────

def _color(code, text):
    if os.environ.get('NO_COLOR') or not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"

def _bold(t):    return _color('1', t)
def _green(t):   return _color('32', t)
def _cyan(t):    return _color('36', t)
def _yellow(t):  return _color('33', t)
def _red(t):     return _color('31', t)
def _dim(t):     return _color('2', t)


# ─── Banner ───────────────────────────────────────────────

BANNER = f"""\
{_bold('EPL')} - English Programming Language {_dim(f'v{__version__}')}
Write code in plain English. Build anything.
"""

HELP = f"""\
{_bold('EPL')} - English Programming Language {_dim(f'v{__version__}')}

{_bold('Usage:')}
  epl <file.epl>                   Run an EPL program
  epl run <file.epl> [flags]       Run an EPL program
  epl new <name> [--template T]    Create a new EPL project
  epl build <file.epl>             Compile to native executable (.exe)
  epl wasm <file.epl>              Compile to WebAssembly (.wasm)
  epl test [dir|file]              Run EPL test suite
  epl repl                         Start interactive REPL
  epl install [--frozen] [package] Install project deps or a package
  epl uninstall <package>          Remove a package
  epl packages                     List installed packages
  epl search <query>               Search available and installed packages
  epl lock                         Generate epl.lock
  epl update [package] [--major]   Update package dependencies
  epl outdated                     Show outdated dependencies
  epl audit                        Verify installed dependency integrity
  epl gitinstall <owner/repo> [as] Install/save a GitHub package dependency
  epl gitremove <name>             Remove a GitHub dependency declaration
  epl gitdeps                      List declared GitHub dependencies
  epl pyinstall <import> [spec]    Install/save a Python package for `Use python`
  epl pyremove <import>            Remove a Python dependency declaration
  epl pydeps                       List declared Python dependencies
  epl modules                      List standard library modules
  epl github clone <owner/repo> [dir]
  epl github pull [path]
  epl github push [path] [-m msg] [--remote name] [--branch name]
  epl serve <file.epl> [options]   Start production web server
  epl deploy <target>              Generate deployment configs
  epl check [file|dir]            Static type checking
  epl fmt <file|dir> [options]     Format EPL source code
  epl lint [dir|file]              Lint EPL source code
  epl docs [dir|file]              Generate API documentation
  epl upgrade                      Update EPL to latest version
  epl version                      Show EPL version
  epl debug <file.epl>             Debug with breakpoints
  epl js <file.epl>                Transpile to JavaScript
  epl node <file.epl>              Transpile to Node.js
  epl kotlin <file.epl>            Transpile to Kotlin
  epl python <file.epl>            Transpile to Python
  epl android <file.epl>           Generate Android project
  epl desktop <file.epl>           Generate desktop app project
  epl web <file.epl>               Generate web app bundle
  epl gui <file.epl>               Run with GUI support
  epl ir <file.epl>                Show LLVM IR
  epl vm <file.epl>                Run with bytecode VM (fast)
  epl micropython <file.epl>       Transpile to MicroPython
  epl benchmark <file.epl>         Benchmark VM vs interpreter
  epl profile <file.epl>           Profile execution
  epl bench                        Run benchmark suite
  epl site [dir]                   Generate docs site
  epl playground                   Start the web playground
  epl notebook                     Start the EPL notebook
  epl blocks                       Start the visual block editor
  epl copilot                      Start AI copilot
  epl lsp                          Start LSP server for IDE
  epl ai <prompt>                  AI code assistant
  epl gen <description>            AI-generate EPL code
  epl explain <file.epl>           AI-explain what code does

{_bold('Flags:')}
  --strict       Enable static type checking
  --check        Run type checker before execution
  --no-color     Disable colored output
  --verbose      Show debug output
  --quiet        Suppress all output except errors
  --sandbox      Disable dangerous builtins
  --interpret    Force tree-walking interpreter
  --json         Output errors as JSON

{_bold('Formatter Options:')}
  --check        Exit with code 1 if formatting would change files
  --in-place     Write formatted output back to files

{_bold('Serve Options:')}
  --port N         Server port (default: 8000)
  --workers N      Number of workers (default: 4)
  --dev            Development mode (built-in server + hot-reload)
  --engine ENGINE  Production server: auto|waitress|gunicorn|uvicorn|builtin
  --reload         Enable hot-reload
  --store TYPE     Store backend: memory|sqlite|redis
  --session TYPE   Session backend: memory|sqlite|redis

{_bold('Android Options:')}
  --build          Build APK after generating project (requires Android SDK)
  --name NAME      Custom app name
  --compose        Use Jetpack Compose UI

{_bold('Package Ecosystem:')}
  epl resolve                      Resolve all dependencies (backtracking)
  epl workspace <cmd>              Workspace/monorepo (init, list, install, validate)
  epl ci [generate|preview]        Generate CI/CD workflows
  epl sync-index [--force]         Sync package index

{_bold('Examples:')}
  epl hello.epl                    Run a program
  epl new myapp --template web     Create a web starter
  epl build myapp/main.epl         Compile to .exe
  epl wasm myapp/main.epl          Compile to .wasm
  epl test tests/                  Run all tests
  epl serve webapp.epl --reload    Dev server with hot-reload
  epl install github:user/lib      Install package from GitHub
  epl install user/lib             Same as GitHub install shorthand
  epl gitinstall epl-lang/web-kit
  epl pyinstall yaml pyyaml>=6     Save/import a pip package with different name
  epl github clone epl-lang/epl
  epl desktop examples/text_editor.epl
  epl workspace init               Initialize monorepo workspace

{_dim(f'EPL v{__version__} | https://github.com/epl-lang/epl')}
"""


def _print_version():
    print(f"epl {__version__}")


def _print_help():
    print(HELP)


# ─── Project Helpers ──────────────────────────────────────

def _load_project_manifest(path='.'):
    """Load epl.toml/epl.json project metadata if present."""
    from epl.package_manager import load_manifest
    try:
        return load_manifest(path)
    except Exception:
        return None


def _default_project_target():
    """Return the configured project entrypoint, if the current directory is a project."""
    manifest = _load_project_manifest('.')
    if not manifest:
        return None
    return manifest.get('entry') or manifest.get('main') or 'main.epl'


_TARGET_OPTION_FLAGS = {
    '--opt',
    '--target',
    '--port',
    '--workers',
    '--store',
    '--session',
}


def _resolve_target_args(args):
    """Use the explicit file argument, otherwise fall back to the project manifest entry."""
    if args:
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith('-'):
                if arg in _TARGET_OPTION_FLAGS and i + 1 < len(args):
                    i += 2
                else:
                    i += 1
                continue
            return list(args)
        target = _default_project_target()
        if target:
            return [target] + list(args)
        return list(args)
    target = _default_project_target()
    if target:
        return [target]
    return None


def _resolve_main_module():
    """Resolve the source-checkout main module without re-importing when possible."""
    main_mod = sys.modules.get('main')
    if main_mod is None:
        main_mod = sys.modules.get('__main__')
    if main_mod is not None and hasattr(main_mod, 'legacy_main'):
        return main_mod

    import importlib

    return importlib.import_module('main')


def _legacy_dispatch(argv):
    """Run a legacy command through the compatibility dispatcher in main.py."""
    return _resolve_main_module().legacy_main(list(argv))


# ─── Command Dispatch ─────────────────────────────────────

def cli_main(argv=None):
    """Main CLI entry point for the `epl` command."""
    if argv is None:
        argv = sys.argv[1:]

    # No args → REPL
    if not argv:
        _run_repl([])
        return 0

    # Global flags
    if '--version' in argv or '-V' in argv:
        _print_version()
        return 0

    if argv[0] in ('--help', '-h', 'help'):
        _print_help()
        return 0

    # Extract global flags
    flags = set()
    clean_args = []
    i = 0
    while i < len(argv):
        if argv[i] in ('--strict', '--no-color', '--verbose', '--quiet', '--sandbox', '--interpret', '--json'):
            flags.add(argv[i])
        else:
            clean_args.append(argv[i])
        i += 1

    if '--no-color' in flags:
        os.environ['NO_COLOR'] = '1'

    # Setup logging
    import logging
    if '--verbose' in flags:
        logging.basicConfig(level=logging.DEBUG, format='%(name)s: %(message)s')
    elif '--quiet' in flags:
        logging.basicConfig(level=logging.ERROR, format='%(message)s')
    else:
        logging.basicConfig(level=logging.WARNING, format='%(message)s')

    if not clean_args:
        _run_repl(flags)
        return 0

    command = clean_args[0]
    rest = clean_args[1:]

    # Command dispatch table
    commands = {
        'run':       lambda: _run_file(rest, flags),
        'new':       lambda: _new_project(rest),
        'build':     lambda: _build(rest, flags, 'build'),
        'compile':   lambda: _build(rest, flags, 'compile'),
        'wasm':      lambda: _wasm(rest),
        'test':      lambda: _run_tests(rest, flags),
        'repl':      lambda: _run_repl(flags),
        'install':   lambda: _pkg_install(rest),
        'uninstall': lambda: _pkg_uninstall(rest),
        'packages':  lambda: _pkg_list(),
        'gitinstall': lambda: _git_install(rest),
        'gitremove': lambda: _git_remove(rest),
        'gitdeps':   lambda: _git_list(),
        'pyinstall': lambda: _py_install(rest),
        'pyremove':  lambda: _py_remove(rest),
        'pydeps':    lambda: _py_list(),
        'modules':   lambda: _list_modules(),
        'github':    lambda: _github(rest),
        'init':      lambda: _init_project(rest),
        'search':    lambda: _pkg_search(rest),
        'add':       lambda: _pkg_add(rest),
        'remove':    lambda: _pkg_remove(rest),
        'lock':      lambda: _pkg_lock(rest),
        'update':    lambda: _pkg_update(rest),
        'tree':      lambda: _pkg_tree(rest),
        'outdated':  lambda: _pkg_outdated(rest),
        'audit':     lambda: _pkg_audit(rest),
        'migrate':   lambda: _pkg_migrate(rest),
        'cache':     lambda: _pkg_cache(rest),
        'publish':   lambda: _pkg_publish(rest),
        'info':      lambda: _pkg_info(rest),
        'stats':     lambda: _pkg_stats(rest),
        'serve':     lambda: _serve(rest),
        'deploy':    lambda: _deploy(rest),
        'fmt':       lambda: _format(rest),
        'lint':      lambda: _lint(rest),
        'check':     lambda: _check(rest, flags),
        'docs':      lambda: _docs(rest),
        'debug':     lambda: _debug(rest, flags),
        'js':        lambda: _transpile_js(rest),
        'node':      lambda: _transpile_node(rest),
        'kotlin':    lambda: _transpile_kotlin(rest),
        'python':    lambda: _transpile_python(rest),
        'android':   lambda: _android(rest),
        'desktop':   lambda: _desktop(rest),
        'web':       lambda: _web(rest),
        'gui':       lambda: _gui(rest),
        'ir':        lambda: _show_ir(rest),
        'vm':        lambda: _run_vm(rest, flags),
        'micropython': lambda: _micropython(rest),
        'benchmark': lambda: _benchmark(rest),
        'profile':   lambda: _profile(rest),
        'bench':     lambda: _bench(rest, flags),
        'site':      lambda: _site(rest),
        'playground': lambda: _playground(rest),
        'notebook':  lambda: _notebook(rest),
        'blocks':    lambda: _blocks(rest),
        'copilot':   lambda: _copilot(rest),
        'lsp':       lambda: _start_lsp(rest),
        'ai':        lambda: _ai(rest),
        'gen':       lambda: _ai_gen(rest),
        'explain':   lambda: _ai_explain(rest),
        'package':   lambda: _package(rest),
        'cloud':     lambda: _cloud(),
        'train':     lambda: _train(),
        'model':     lambda: _model(),
        'resolve':   lambda: _resolve(),
        'workspace': lambda: _workspace(rest),
        'ci':        lambda: _ci(rest),
        'sync-index': lambda: _sync_index(rest),
        'upgrade':   lambda: _upgrade(),
        'version':   lambda: print(f'EPL v{__version__}'),
    }

    if command in commands:
        try:
            return commands[command]() or 0
        except KeyboardInterrupt:
            print(f"\n{_dim('Interrupted.')}")
            return 130
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else 1
        except Exception as e:
            from epl.errors import EPLError
            if isinstance(e, EPLError):
                print(str(e), file=sys.stderr)
            else:
                print(f"{_red('Error:')} {e}", file=sys.stderr)
            return 1

    # Default: treat as filename
    if command.endswith('.epl') or os.path.isfile(command):
        try:
            return _run_file([command] + rest, flags) or 0
        except KeyboardInterrupt:
            print(f"\n{_dim('Interrupted.')}")
            return 130
        except Exception as e:
            from epl.errors import EPLError
            if isinstance(e, EPLError):
                print(str(e), file=sys.stderr)
            else:
                print(f"{_red('Error:')} {e}", file=sys.stderr)
            return 1

    print(f"{_red('Unknown command:')} {command}")
    print(f"Run {_bold('epl --help')} for usage.")
    return 1


# ─── Run ──────────────────────────────────────────────────

def _run_file(args, flags):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        print("Usage: epl run <file.epl>")
        print("       or run from a directory containing epl.toml / epl.json")
        return 1

    filename = args[0]
    if not os.path.isfile(filename):
        print(f"{_red('Error:')} File not found: {filename}")
        return 1

    main_mod = _resolve_main_module()
    main_mod.run_file(
        filename,
        strict='--strict' in flags,
        safe_mode='--sandbox' in flags,
        force_interpret='--interpret' in flags,
        json_errors='--json' in flags,
    )
    return 0


# ─── New Project ──────────────────────────────────────────

def _new_project(args):
    """Create a new EPL project with full structure."""
    if not args:
        print(f"{_red('Error:')} No project name specified.")
        print(f"Usage: epl new <project-name> [--template basic|web|api|cli|lib]")
        return 1

    name = args[0]
    template = 'basic'
    if '--template' in args:
        idx = args.index('--template')
        if idx + 1 >= len(args):
            print(f"{_red('Error:')} Missing template name after --template.")
            return 1
        template = args[idx + 1].lower()

    valid_templates = {'basic', 'web', 'api', 'cli', 'lib'}
    if template not in valid_templates:
        print(f"{_red('Error:')} Unknown template: {template}")
        print("Available templates: basic, web, api, cli, lib")
        return 1

    # Validate project name
    import re
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', name):
        print(f"{_red('Error:')} Invalid project name: {name}")
        print("Use letters, digits, hyphens, underscores. Must start with a letter.")
        return 1

    if os.path.exists(name):
        print(f"{_red('Error:')} Directory '{name}' already exists.")
        return 1

    # Create project structure
    os.makedirs(name)
    os.makedirs(os.path.join(name, 'src'))
    os.makedirs(os.path.join(name, 'tests'))
    os.makedirs(os.path.join(name, 'lib'))

    manifest_data, main_source, test_source, readme_body = _project_template(name, template)

    # epl.toml manifest
    from epl.package_manager import _dump_toml, _manifest_to_toml
    toml_data = _manifest_to_toml(manifest_data)
    with open(os.path.join(name, 'epl.toml'), 'w', encoding='utf-8') as f:
        f.write(_dump_toml(toml_data) + '\n')

    with open(os.path.join(name, 'src', 'main.epl'), 'w', encoding='utf-8') as f:
        f.write(main_source)

    with open(os.path.join(name, 'tests', 'test_main.epl'), 'w', encoding='utf-8') as f:
        f.write(test_source)

    with open(os.path.join(name, 'README.md'), 'w', encoding='utf-8') as f:
        f.write(readme_body)

    # .gitignore
    with open(os.path.join(name, '.gitignore'), 'w', encoding='utf-8') as f:
        f.write('# EPL\nepl_modules/\n*.exe\n*.o\nbuild/\ndist/\n')
        f.write('# Python\n__pycache__/\n*.pyc\n.venv/\n')
        f.write('# IDE\n.vscode/\n.idea/\n')

    print(f"\n  {_green('Created')} EPL project: {_bold(name)} {_dim(f'[{template}]')}")
    print(f"\n  {_dim('Project structure:')}")
    print(f"    {name}/")
    print(f"    ├── epl.toml          Project manifest")
    print(f"    ├── README.md         Documentation")
    print(f"    ├── .gitignore        Git ignore rules")
    print(f"    ├── src/")
    print(f"    │   └── main.epl      Entry point")
    print(f"    ├── tests/")
    print(f"    │   └── test_main.epl Test file")
    print(f"    └── lib/              Local libraries")
    print(f"\n  {_dim('Get started:')}")
    print(f"    cd {name}")
    print(f"    epl install                  {_dim('# sync EPL, GitHub, and Python dependencies')}")
    print(f"    epl run                      {_dim('# uses the manifest entrypoint')}")
    if template in ('web', 'api', 'lib'):
        print(f"    epl test tests/             {_dim('# run the starter tests')}")
    if template in ('web', 'api'):
        print(f"    epl serve                   {_dim('# boot the generated web app')}")
    print(f"    epl pyinstall requests       {_dim('# add a Python package for `Use python`')}")
    print(f"    epl gitinstall owner/repo    {_dim('# add a GitHub EPL package')}")
    print()
    return 0


def _project_template(name, template):
    dependencies = {}
    scripts = {
        "start": "epl run src/main.epl",
        "test": "epl test tests/",
        "build": "epl build src/main.epl",
    }
    description = f"{name} — an EPL project"

    if template == 'web':
        description = f"{name} — EPL web application"
        dependencies = {"epl-web": f"^{__version__}"}
        scripts["serve"] = "epl serve src/main.epl"
        main_source = (
            f'Note: {name} web app template\n'
            'Import "epl-web"\n\n'
            f'Create app equal to create_app("{name}")\n\n'
            'Call get_route(app, "/", Function()\n'
            f'    Return html_response("<h1>{name}</h1><p>EPL web template ready.</p>", 200)\n'
            'End)\n\n'
            'Call get_route(app, "/api/health", Function()\n'
            f'    Return json_response(Map with status = "ok" and app = "{name}", 200)\n'
            'End)\n'
        )
        test_source = (
            'Import "epl-test"\n\n'
            'Call test("web template smoke", Function()\n'
            '    Call expect_equal(1 + 1, 2, "basic arithmetic still works")\n'
            'End)\n\n'
            'Call test_summary()\n'
        )
        readme_body = _template_readme(
            name,
            template,
            [
                "epl install",
                "epl serve",
                "epl run",
            ],
            "Starter web app using the supported `epl-web` facade package.",
        )
    elif template == 'api':
        description = f"{name} — EPL API service"
        dependencies = {"epl-web": f"^{__version__}", "epl-db": f"^{__version__}"}
        scripts["serve"] = "epl serve src/main.epl"
        main_source = (
            f'Note: {name} API template\n'
            'Import "epl-web"\n'
            'Import "epl-db"\n\n'
            'db = open(":memory:")\n'
            'Call create_table(db, "items", Map with id = "INTEGER" and name = "TEXT")\n'
            'Call execute(db, "INSERT INTO items (id, name) VALUES (1, \'example item\')")\n\n'
            f'Create app equal to create_app("{name}")\n\n'
            'Call get_route(app, "/api/health", Function()\n'
            f'    Return json_response(Map with status = "ok" and service = "{name}", 200)\n'
            'End)\n\n'
            'Call get_route(app, "/api/items", Function()\n'
            '    items = query(db, "SELECT id, name FROM items ORDER BY id")\n'
            '    Return json_response(Map with items = items, 200)\n'
            'End)\n'
        )
        test_source = (
            'Import "epl-test"\n\n'
            'Call test("api template smoke", Function()\n'
            '    Call expect_true(True, "starter API test")\n'
            'End)\n\n'
            'Call test_summary()\n'
        )
        readme_body = _template_readme(
            name,
            template,
            [
                "epl install",
                "epl serve",
                "epl run",
            ],
            "Starter API app using the supported `epl-web` and `epl-db` facade packages.",
        )
    elif template == 'cli':
        description = f"{name} — EPL CLI tool"
        main_source = (
            f'Note: {name} CLI template\n\n'
            f'Say "Welcome to {name}."\n'
            'Say "Edit src/main.epl to add your CLI behavior."\n'
        )
        test_source = (
            f'Note: Tests for {name}\n\n'
            'Assert 1 + 1 == 2\n'
            'Assert length("hello") == 5\n'
            'Say "All tests passed!"\n'
        )
        readme_body = _template_readme(
            name,
            template,
            [
                "epl run",
                "epl build",
                "epl test tests/",
            ],
            "Starter CLI project with a simple command-line oriented entrypoint.",
        )
    elif template == 'lib':
        description = f"{name} — EPL library package"
        dependencies = {"epl-test": f"^{__version__}"}
        main_source = (
            f'Note: {name} library template\n\n'
            'Define Function greet Takes name\n'
            '    Return "Hello, " + name + "!"\n'
            'End\n'
        )
        test_source = (
            'Import "src/main.epl"\n'
            'Import "epl-test"\n\n'
            'Call test("greet returns a message", Function()\n'
            f'    Call expect_equal(greet("EPL"), "Hello, EPL!", "{name} greet helper")\n'
            'End)\n\n'
            'Call test_summary()\n'
        )
        readme_body = _template_readme(
            name,
            template,
            [
                "epl install",
                "epl test tests/",
                "epl run src/main.epl",
            ],
            "Starter reusable EPL library with tests using the supported `epl-test` facade package.",
        )
    else:
        main_source = (
            f'Note: {name} — Created with EPL v{__version__}\n\n'
            f'Say "Hello from {name}!"\n'
            'Say "Edit src/main.epl to get started."\n'
        )
        test_source = (
            f'Note: Tests for {name}\n\n'
            'Assert 1 + 1 == 2\n'
            'Assert length("hello") == 5\n'
            'Say "All tests passed!"\n'
        )
        readme_body = _template_readme(
            name,
            template,
            [
                "epl run",
                "epl test tests/",
                "epl build",
            ],
            "Starter EPL project.",
        )

    manifest = {
        "name": name,
        "version": "1.0.0",
        "description": description,
        "entry": "src/main.epl",
        "author": "",
        "scripts": scripts,
        "dependencies": dependencies,
    }
    return manifest, main_source, test_source, readme_body


def _template_readme(name, template, commands, summary):
    command_block = '\n'.join(commands)
    return (
        f'# {name}\n\n'
        f'{summary}\n\n'
        f'## Template\n\n'
        f'- `{template}`\n\n'
        f'## Getting Started\n\n'
        f'```bash\n'
        f'cd {name}\n'
        f'{command_block}\n'
        f'```\n\n'
        f'## Project Workflows\n\n'
        f'```bash\n'
        f'# Sync manifest-managed dependencies\n'
        f'epl install\n\n'
        f'# Add a Python package for `Use python`\n'
        f'epl pyinstall requests\n\n'
        f'# Add a GitHub EPL package dependency\n'
        f'epl gitinstall owner/repo alias\n\n'
        f'# Clone, pull, or push GitHub projects\n'
        f'epl github clone owner/repo\n'
        f'epl github pull\n'
        f'epl github push . -m "Update project"\n'
        f'```\n'
    )


# ─── Build / Compile ─────────────────────────────────────

def _build(args, flags, command='build'):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified and no epl.toml/epl.json project was found.")
        return 1
    filename = args[0]
    opt_level = 2
    static_link = command == 'build'
    target = None

    i = 1
    while i < len(args):
        arg = args[i]
        if arg == '--opt' and i + 1 < len(args):
            opt_level = int(args[i + 1])
            i += 2
            continue
        if arg.startswith('--opt='):
            opt_level = int(arg.split('=', 1)[1])
            i += 1
            continue
        if arg == '--static':
            static_link = True
            i += 1
            continue
        if arg == '--no-static':
            static_link = False
            i += 1
            continue
        if arg == '--target' and i + 1 < len(args):
            target = args[i + 1]
            i += 2
            continue
        if arg.startswith('--target='):
            target = arg.split('=', 1)[1]
            i += 1
            continue
        print(f"{_red('Error:')} Unknown {command} option: {arg}")
        return 1

    try:
        main_mod = _resolve_main_module()
        return 0 if main_mod.compile_file(filename, opt_level=opt_level, static=static_link, target=target) else 1
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _run_tests(args, flags):
    from fnmatch import fnmatch
    from epl.test_framework import EPLTestRunner

    targets = list(args)
    if not targets:
        targets = ['tests'] if os.path.isdir('tests') else ['.']

    discovered = []
    seen = set()

    for target in targets:
        if os.path.isdir(target):
            for root, _, files in os.walk(target):
                for filename in sorted(files):
                    if not filename.endswith('.epl'):
                        continue
                    if not (fnmatch(filename, 'test_*.epl') or fnmatch(filename, '*_test.epl')):
                        continue
                    test_file = os.path.join(root, filename)
                    normalized = os.path.normcase(os.path.abspath(test_file))
                    if normalized in seen:
                        continue
                    seen.add(normalized)
                    discovered.append(test_file)
        elif os.path.isfile(target) and target.endswith('.epl'):
            normalized = os.path.normcase(os.path.abspath(target))
            if normalized not in seen:
                seen.add(normalized)
                discovered.append(target)
        else:
            print(f"{_yellow('Skip:')} {target} is not an .epl file or directory")

    if not discovered:
        print(f"{_red('Error:')} No EPL test files found.")
        return 1

    runner = EPLTestRunner(
        verbose='--quiet' not in flags,
        color='--no-color' not in flags,
    )

    for test_file in discovered:
        runner.run_file(test_file)

    return 0 if runner.report() else 1


def _run_repl(flags):
    try:
        main_mod = _resolve_main_module()
        main_mod.run_repl()
        return 0
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _pkg_install(args):
    from epl.package_manager import install_dependencies, install_package

    frozen = '--frozen' in args
    no_save = '--no-save' in args
    local = '--local' in args
    clean_args = [a for a in args if a not in ('--frozen', '--no-save', '--local')]

    if not clean_args:
        return 0 if install_dependencies('.', frozen=frozen) else 1

    if frozen:
        print(f"{_red('Error:')} `--frozen` applies to project dependency installs, not ad hoc package installs.")
        return 1

    return 0 if install_package(clean_args[0], save=not no_save, local=local, project_path='.') else 1


def _pkg_uninstall(args):
    from epl.package_manager import uninstall_package

    if not args:
        print(f"{_red('Error:')} No package specified.")
        return 1
    return 0 if uninstall_package(args[0]) else 1


def _pkg_list():
    from epl.package_manager import list_packages

    packages = list_packages()
    if packages:
        print("\n  Installed Packages")
        print("  " + "-" * 40)
        for name, version, desc in packages:
            print(f"  {name} @ {version}  {desc}")
    else:
        print("  No packages installed.")
    return 0


def _pkg_add(args):
    from epl.package_manager import add_dependency

    if not args:
        print(f"{_red('Error:')} No package specified.")
        print("Usage: epl add <package> [version] [--dev]")
        return 1

    dev = '--dev' in args
    clean_args = [arg for arg in args if not arg.startswith('--')]
    if not clean_args:
        print(f"{_red('Error:')} No package specified.")
        return 1

    name = clean_args[0]
    version_spec = clean_args[1] if len(clean_args) > 1 else '*'
    return 0 if add_dependency(name, version_spec, path='.', dev=dev) else 1


def _pkg_remove(args):
    from epl.package_manager import remove_dependency

    if not args:
        print(f"{_red('Error:')} No package specified.")
        print("Usage: epl remove <package>")
        return 1

    return 0 if remove_dependency(args[0], path='.') else 1


def _pkg_tree(args):
    from epl.package_manager import print_dependency_tree

    if args:
        print(f"{_red('Error:')} `epl tree` does not accept positional arguments.")
        return 1

    print_dependency_tree('.')
    return 0


def _pkg_search(args):
    from epl.package_manager import search_packages

    if not args:
        print(f"{_red('Error:')} No search query specified.")
        print("Usage: epl search <query>")
        return 1

    results = search_packages(' '.join(args))
    if not results:
        print("  No packages found.")
        return 0

    print(f"\n  {_bold('Package Search Results')} ({len(results)}):")
    print("  " + "-" * 72)
    for result in results:
        version = result.get('latest') or result.get('version', '?')
        source = result.get('source', 'unknown')
        description = result.get('description', '')
        print(f"  {result['name']:<24} {version:<12} {source:<12} {description}")
    print()
    return 0


def _pkg_lock(args):
    from epl.package_manager import create_lockfile

    if args:
        print(f"{_red('Error:')} `epl lock` does not accept positional arguments.")
        return 1
    return 0 if create_lockfile('.') is not None else 1


def _pkg_update(args):
    from epl.package_manager import update_all, update_package

    allow_major = '--major' in args
    clean_args = [a for a in args if a != '--major']
    if clean_args:
        return 0 if update_package(clean_args[0], '.', allow_major=allow_major) else 1
    return 0 if update_all('.', allow_major=allow_major) else 1


def _pkg_outdated(args):
    from epl.package_manager import outdated_packages

    if args:
        print(f"{_red('Error:')} `epl outdated` does not accept positional arguments.")
        return 1

    results = outdated_packages('.')
    if not results:
        print("  All packages up to date.")
        return 0

    print(f"  {'Package':<24} {'Current':<12} {'Latest':<12} {'Constraint':<14}")
    print(f"  {'─' * 68}")
    for item in results:
        note = " major" if item.get('major_update') else ""
        print(
            f"  {item['name']:<24} {item['current']:<12} {item['latest']:<12} "
            f"{item.get('constraint', '*'):<14}{note}"
        )
    print("\n  Run `epl update` to update compatible versions or `epl update --major` to allow major bumps.")
    return 0


def _pkg_audit(args):
    from epl.package_manager import audit_packages

    if args:
        print(f"{_red('Error:')} `epl audit` does not accept positional arguments.")
        return 1

    results = audit_packages('.')
    print(f"\n  {_bold('Package Audit')}")
    print(f"  {'─' * 40}")
    print(f"  Packages OK: {results['ok']}")
    if results['warnings']:
        print(f"  Warnings: {len(results['warnings'])}")
        for warning in results['warnings']:
            print(f"    - {warning}")
    if results['errors']:
        print(f"  Errors: {len(results['errors'])}")
        for error in results['errors']:
            print(f"    - {error}")
        return 1
    if not results['warnings']:
        print("  No problems found.")
    return 0


def _pkg_migrate(args):
    from epl.package_manager import migrate_manifest_to_toml

    if args:
        print(f"{_red('Error:')} `epl migrate` does not accept positional arguments.")
        return 1

    if migrate_manifest_to_toml('.'):
        print("  Migration complete. You can now delete epl.json.")
    else:
        print("  Nothing to migrate (already using epl.toml or no epl.json found).")
    return 0


def _pkg_cache(args):
    import glob
    from epl.package_manager import CACHE_DIR, clean_cache

    subcommand = args[0] if args else 'info'
    if subcommand == 'clean':
        if len(args) > 1:
            print(f"{_red('Error:')} `epl cache clean` does not accept additional arguments.")
            return 1
        clean_cache()
        return 0
    if subcommand != 'info':
        print(f"{_red('Error:')} Unknown cache command: {subcommand}")
        return 1

    files = glob.glob(os.path.join(CACHE_DIR, '*')) if os.path.isdir(CACHE_DIR) else []
    total = sum(os.path.getsize(path) for path in files if os.path.isfile(path))
    print(f"  Cache: {len(files)} files, {total / 1024:.1f} KB")
    print(f"  Path: {CACHE_DIR}")
    return 0


def _pkg_publish(args):
    from epl.registry import registry_publish

    repo = None
    path = '.'
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--repo' and i + 1 < len(args):
            repo = args[i + 1]
            i += 2
            continue
        if arg.startswith('--'):
            print(f"{_red('Error:')} Unknown publish option: {arg}")
            return 1
        path = arg
        i += 1

    registry_publish(path, repo=repo)
    return 0


def _pkg_info(args):
    from epl.registry import registry_info

    if len(args) != 1:
        print(f"{_red('Error:')} Usage: epl info <package-name>")
        return 1

    registry_info(args[0])
    return 0


def _pkg_stats(args):
    from epl.registry import registry_stats

    if args:
        print(f"{_red('Error:')} `epl stats` does not accept positional arguments.")
        return 1

    registry_stats()
    return 0


def _git_install(args):
    if not args:
        print(f"{_red('Error:')} No GitHub repository specified.")
        print("Usage: epl gitinstall <owner/repo> [alias]")
        return 1
    from epl.package_manager import add_github_dependency
    repo = args[0]
    alias = args[1] if len(args) > 1 and not args[1].startswith('--') else None
    return 0 if add_github_dependency(repo, alias=alias, save='--no-save' not in args, path='.') else 1


def _git_remove(args):
    if not args:
        print(f"{_red('Error:')} No GitHub dependency name specified.")
        print("Usage: epl gitremove <name-or-owner/repo>")
        return 1
    from epl.package_manager import remove_github_dependency
    return 0 if remove_github_dependency(args[0], '.') else 1


def _git_list():
    from epl.package_manager import list_github_dependencies

    deps = list_github_dependencies('.')
    if not deps:
        print("  No GitHub dependencies declared.")
        return 0

    print(f"\n  {_bold('Declared GitHub Dependencies')} ({len(deps)}):")
    print("  " + "-" * 40)
    for alias, repo in deps:
        print(f"  {alias:20s} -> {repo}")
    print()
    return 0


def _py_install(args):
    from epl.package_manager import install_python_dependencies, install_python_package

    if not args:
        return 0 if install_python_dependencies('.') else 1

    no_save = '--no-save' in args
    clean_args = [a for a in args if a != '--no-save']
    import_name = clean_args[0]
    requirement = clean_args[1] if len(clean_args) > 1 else None
    return 0 if install_python_package(import_name, requirement, save=not no_save, project_path='.') else 1


def _py_remove(args):
    if not args:
        print(f"{_red('Error:')} No Python import name specified.")
        print("Usage: epl pyremove <import-name>")
        return 1
    from epl.package_manager import remove_python_dependency
    return 0 if remove_python_dependency(args[0], '.') else 1


def _py_list():
    from epl.package_manager import list_python_dependencies

    deps = list_python_dependencies('.')
    if not deps:
        print("  No Python dependencies declared.")
        return 0

    print(f"\n  {_bold('Declared Python Dependencies')} ({len(deps)}):")
    print("  " + "-" * 40)
    for import_name, requirement in deps:
        display = import_name if requirement in ('', '*') else requirement
        print(f"  {import_name:20s} -> {display}")
    print()
    return 0


def _github(args):
    if not args:
        print(f"{_red('Error:')} No GitHub subcommand specified.")
        print("Usage: epl github <clone|pull|push> ...")
        return 1

    from epl.github_tools import clone_repo, pull_repo, push_repo

    subcommand = args[0]
    if subcommand == 'clone':
        if len(args) < 2:
            print("Usage: epl github clone <owner/repo> [dir]")
            return 1
        repo = args[1]
        dest = args[2] if len(args) > 2 and not args[2].startswith('--') else None
        return 0 if clone_repo(repo, dest=dest) else 1

    if subcommand == 'pull':
        path = args[1] if len(args) > 1 else '.'
        return 0 if pull_repo(path) else 1

    if subcommand == 'push':
        path = '.'
        message = 'Update via EPL'
        remote = 'origin'
        branch = None
        i = 1
        if i < len(args) and not args[i].startswith('-'):
            path = args[i]
            i += 1
        while i < len(args):
            arg = args[i]
            if arg in ('-m', '--message') and i + 1 < len(args):
                message = args[i + 1]
                i += 2
                continue
            if arg == '--remote' and i + 1 < len(args):
                remote = args[i + 1]
                i += 2
                continue
            if arg == '--branch' and i + 1 < len(args):
                branch = args[i + 1]
                i += 2
                continue
            print(f"{_red('Error:')} Unknown github push option: {arg}")
            return 1
        return 0 if push_repo(path=path, message=message, remote=remote, branch=branch) else 1

    print(f"{_red('Error:')} Unknown github subcommand: {subcommand}")
    return 1


def _init_project(args):
    from epl.package_manager import init_project

    if len(args) > 1:
        print(f"{_red('Error:')} Usage: epl init [name]")
        return 1

    init_project(args[0] if args else None)
    return 0


def _upgrade():
    """Self-update EPL to the latest version."""
    import subprocess
    print("  Checking for EPL updates...")
    
    # Try pip upgrade (works if EPL was installed via pip)
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'epl-lang'],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and 'already satisfied' not in result.stdout.lower():
            print("  EPL updated successfully via pip!")
            return 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Try git pull (works if EPL was cloned from GitHub)
    epl_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_dir = os.path.join(epl_root, '.git')
    if os.path.isdir(git_dir):
        try:
            result = subprocess.run(
                ['git', 'pull', '--rebase'],
                cwd=epl_root, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                print(f"  EPL updated via git: {result.stdout.strip()}")
                return 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    print(f"  EPL is at v{__version__}. No update method available.")
    print("  To update manually: git pull  or  pip install --upgrade epl-lang")
    return 0


def _read_epl_source(filepath):
    if not os.path.isfile(filepath):
        raise FileNotFoundError(filepath)
    with open(filepath, 'r', encoding='utf-8') as handle:
        return handle.read()


def _parse_epl_program(source, filepath):
    from epl.errors import set_source_context
    from epl.lexer import Lexer
    from epl.parser import Parser

    set_source_context(source, filepath)
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def _collect_epl_files(targets):
    from pathlib import Path

    files = []
    missing = []
    seen = set()

    for target in targets:
        path = Path(target)
        if path.is_dir():
            for child in sorted(path.rglob('*.epl')):
                key = str(child.resolve())
                if key not in seen:
                    files.append(child)
                    seen.add(key)
        elif path.is_file():
            key = str(path.resolve())
            if key not in seen:
                files.append(path)
                seen.add(key)
        else:
            missing.append(target)

    return files, missing


def _find_web_app(env):
    from epl.web import EPLWebApp

    for binding in getattr(env, 'variables', {}).values():
        value = binding.get('value') if isinstance(binding, dict) else binding
        if isinstance(value, EPLWebApp):
            return value
    for module_env in getattr(env, 'modules', {}).values():
        found = _find_web_app(module_env)
        if found is not None:
            return found
    return None


def _load_epl_web_app(filepath):
    from epl.interpreter import Interpreter

    source = _read_epl_source(filepath)
    program = _parse_epl_program(source, filepath)
    interpreter = Interpreter()
    interpreter.execute(program)

    app = getattr(interpreter, '_web_app', None)
    if app is None:
        app = _find_web_app(interpreter.global_env)
    if app is None:
        raise RuntimeError("No web app found in EPL file. Use 'Create App ...' or the epl-web facade package.")
    return app, interpreter


def _load_epl_program(filepath):
    source = _read_epl_source(filepath)
    return source, _parse_epl_program(source, filepath)


def _write_generated_text(source_file, extension, content):
    output_path = os.path.splitext(os.path.basename(source_file))[0] + extension
    with open(output_path, 'w', encoding='utf-8') as handle:
        handle.write(content)
    return output_path


def _serve(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified and no epl.toml/epl.json project was found.")
        return 1

    filename = args[0]
    port = 8000
    workers = 4
    reload_mode = False
    dev_mode = False
    store_backend = 'memory'
    session_backend = 'memory'
    engine = 'auto'

    i = 1
    while i < len(args):
        arg = args[i]
        if arg == '--port' and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
            continue
        if arg == '--workers' and i + 1 < len(args):
            workers = int(args[i + 1])
            i += 2
            continue
        if arg == '--reload':
            reload_mode = True
            i += 1
            continue
        if arg == '--dev':
            dev_mode = True
            reload_mode = True
            i += 1
            continue
        if arg == '--engine' and i + 1 < len(args):
            engine = args[i + 1].lower()
            valid_engines = ('auto', 'waitress', 'gunicorn', 'uvicorn', 'builtin')
            if engine not in valid_engines:
                print(f"{_red('Error:')} Unknown engine: {engine}")
                print(f"Valid engines: {', '.join(valid_engines)}")
                return 1
            i += 2
            continue
        if arg == '--store' and i + 1 < len(args):
            store_backend = args[i + 1]
            i += 2
            continue
        if arg == '--session' and i + 1 < len(args):
            session_backend = args[i + 1]
            i += 2
            continue
        print(f"{_red('Error:')} Unknown serve option: {arg}")
        return 1

    try:
        from epl.store_backends import configure_backends
        configure_backends(store=store_backend, session=session_backend)

        if dev_mode:
            # Development mode: use built-in threaded server with hot-reload
            from epl.web import start_server
            app, interpreter = _load_epl_web_app(filename)
            print(f"  {_yellow('⚠ Development mode')} — not for production use")
            if reload_mode:
                try:
                    from epl.hot_reload import start_with_reload
                    start_with_reload(filename, port=port)
                except ImportError:
                    start_server(app, port=port, interpreter=interpreter, workers=workers)
            else:
                start_server(app, port=port, interpreter=interpreter, workers=workers)
        else:
            # Production mode: use WSGI adapter with best available server
            from epl.deploy import WSGIAdapter, serve
            app, interpreter = _load_epl_web_app(filename)

            # Auto-install waitress on Windows if no production server found
            if engine == 'auto':
                _ensure_production_server()

            serve(
                WSGIAdapter(app, interpreter=interpreter),
                host='0.0.0.0',
                port=port,
                workers=workers,
                reload=reload_mode,
                engine=engine if engine != 'auto' else None,
            )
        return 0
    except ValueError as exc:
        print(f"{_red('Error:')} {exc}")
        return 1
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}")
        return 1


def _ensure_production_server():
    """Try to ensure at least one production WSGI server is available."""
    for mod_name in ('waitress', 'gunicorn', 'uvicorn'):
        try:
            __import__(mod_name)
            return  # found one
        except ImportError:
            continue
    # None found — try to install waitress (cross-platform, lightweight)
    print(f"  {_yellow('Note:')} No production server found. Installing waitress...")
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'waitress'],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            print(f"  {_green('✓')} waitress installed successfully.")
        else:
            print(f"  {_yellow('⚠')} Could not install waitress. Using built-in server.")
            print(f"  Install manually: pip install waitress")
    except Exception:
        print(f"  {_yellow('⚠')} Could not install waitress. Using built-in server.")
        print(f"  Install manually: pip install waitress")


def _deploy(args):
    from epl.deploy import deploy_cli

    if not args:
        deploy_cli([])
        return 0

    valid_targets = ('gunicorn', 'nginx', 'tomcat', 'docker', 'systemd', 'asgi', 'all')
    if args[0] not in valid_targets:
        print(f"{_red('Error:')} Unknown deploy target '{args[0]}'")
        print(f"Valid targets: {', '.join(valid_targets)}")
        return 1

    deploy_cli(list(args))
    return 0


def _format(args):
    from pathlib import Path
    from epl.formatter import format_source

    check_only = '--check' in args
    in_place = '--in-place' in args
    targets = [a for a in args if a not in ('--check', '--in-place')]

    if not targets:
        if os.path.isdir('src'):
            targets = ['src']
        elif os.path.isfile(_default_project_target() or ''):
            targets = [_default_project_target()]
        else:
            print(f"{_red('Error:')} No file or directory specified.")
            print("Usage: epl fmt <file|dir> [--check] [--in-place]")
            return 1

    files = []
    seen = set()
    for target in targets:
        path = Path(target)
        if path.is_dir():
            for child in sorted(path.rglob('*.epl')):
                child_key = str(child.resolve())
                if child_key not in seen:
                    files.append(child)
                    seen.add(child_key)
        elif path.is_file():
            child_key = str(path.resolve())
            if child_key not in seen:
                files.append(path)
                seen.add(child_key)
        else:
            print(f"{_yellow('Skip:')} {target} not found")

    if not files:
        print(f"{_red('Error:')} No .epl files found.")
        return 1

    changed = []
    unchanged = []
    outputs = []

    for filepath in files:
        original = filepath.read_text(encoding='utf-8')
        formatted = format_source(original)
        if formatted != original:
            changed.append(str(filepath))
            if in_place:
                filepath.write_text(formatted, encoding='utf-8')
            elif not check_only:
                outputs.append((str(filepath), formatted))
        else:
            unchanged.append(str(filepath))

    if check_only:
        for filepath in changed:
            print(f"  NEEDS FORMATTING: {filepath}")
        if not changed:
            print(f"  {_green('All files already formatted.')}")
        return 1 if changed else 0

    if in_place:
        for filepath in changed:
            print(f"  FORMATTED: {filepath}")
        for filepath in unchanged:
            print(f"  OK: {filepath}")
        return 0

    if len(outputs) == 1:
        print(outputs[0][1], end='')
        return 0

    for idx, (filepath, content) in enumerate(outputs):
        if idx:
            print()
        print(f"--- {filepath} ---")
        print(content, end='')
    return 0


def _lint(args):
    import json
    from epl.doc_linter import Linter, LintConfig

    fix_mode = False
    config_path = None
    output_format = 'text'
    max_line_length = 120
    targets = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--fix':
            fix_mode = True
            i += 1
            continue
        if arg == '--config' and i + 1 < len(args):
            config_path = args[i + 1]
            i += 2
            continue
        if arg == '--max-line-length' and i + 1 < len(args):
            max_line_length = int(args[i + 1])
            i += 2
            continue
        if arg == '--format' and i + 1 < len(args):
            output_format = args[i + 1]
            i += 2
            continue
        targets.append(arg)
        i += 1

    if output_format not in ('text', 'json'):
        print(f"{_red('Error:')} Unknown lint output format: {output_format}")
        return 1

    if not targets:
        targets = ['.']

    config = LintConfig.from_file(config_path) if config_path else LintConfig()
    config.max_line_length = max_line_length
    linter = Linter(config)

    files, missing = _collect_epl_files(targets)
    for target in missing:
        print(f"{_yellow('Skip:')} {target} not found")

    if not files:
        print(f"{_red('Error:')} No .epl files found.")
        return 1

    all_issues = []
    for filepath in files:
        all_issues.extend(linter.lint_file(str(filepath)))

    if fix_mode:
        fix_total = 0
        for filepath in files:
            _, count = linter.auto_fix(str(filepath))
            fix_total += count
        print(f"  Fixed {fix_total} issues")
        return 0

    if output_format == 'json':
        payload = [
            {
                'file': issue.file,
                'line': issue.line,
                'col': issue.column,
                'severity': issue.severity,
                'rule': issue.rule,
                'message': issue.message,
            }
            for issue in all_issues
        ]
        print(json.dumps(payload, indent=2))
    else:
        print(linter.format_report(all_issues))

    return 1 if any(issue.severity == 'error' for issue in all_issues) else 0


def _check(args, flags):
    """Run static type checking on EPL files."""
    import glob

    strict = '--strict' in flags
    targets = [a for a in args if not a.startswith('--')]

    if not targets:
        # Auto-discover: check for epl.toml entry or src/ directory
        target = _default_project_target()
        if target and os.path.isfile(target):
            targets = [target]
        elif os.path.isdir('src'):
            targets = glob.glob('src/**/*.epl', recursive=True)
        else:
            targets = glob.glob('**/*.epl', recursive=True)

    if not targets:
        print(f"{_red('Error:')} No .epl files found.")
        return 1

    from epl.type_checker import type_check_file

    total_errors = 0
    total_warnings = 0
    total_infos = 0

    for filepath in sorted(targets):
        if not os.path.isfile(filepath):
            # Might be a directory
            if os.path.isdir(filepath):
                targets.extend(glob.glob(os.path.join(filepath, '**/*.epl'), recursive=True))
                continue
            print(f"{_yellow('Skip:')} {filepath} not found")
            continue

        try:
            checker = type_check_file(filepath, strict=strict)
            errors = [w for w in checker.warnings if w.severity == 'error']
            warns = [w for w in checker.warnings if w.severity == 'warning']
            infos = [w for w in checker.warnings if w.severity == 'info']

            total_errors += len(errors)
            total_warnings += len(warns)
            total_infos += len(infos)

            if checker.warnings:
                print(f"\n  {_bold(filepath)}")
                print(checker.format_report())
        except Exception as e:
            print(f"\n  {_bold(filepath)}")
            print(f"  {_red('Parse Error:')} {e}")
            total_errors += 1

    # Summary
    print(f"\n{'─' * 50}")
    print(f"  {_bold('Type Check Summary')}: "
          f"{len(targets)} file(s) checked")
    if total_errors:
        print(f"  {_red(f'{total_errors} error(s)')}, "
              f"{_yellow(f'{total_warnings} warning(s)')}, "
              f"{total_infos} info(s)")
    elif total_warnings:
        print(f"  {_green('No errors.')} "
              f"{_yellow(f'{total_warnings} warning(s)')}, "
              f"{total_infos} info(s)")
    else:
        print(f"  {_green('All checks passed!')} "
              f"{total_infos} info(s)")

    return 1 if total_errors > 0 else 0


def _docs(args):
    from pathlib import Path
    from epl.doc_linter import DocGenerator

    output_dir = 'docs'
    output_format = 'all'
    targets = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('-o', '--output') and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
            continue
        if arg in ('-f', '--format') and i + 1 < len(args):
            output_format = args[i + 1]
            i += 2
            continue
        targets.append(arg)
        i += 1

    if output_format not in ('html', 'markdown', 'json', 'all'):
        print(f"{_red('Error:')} Unknown docs format: {output_format}")
        return 1

    if not targets:
        targets = ['src'] if os.path.isdir('src') else ['.']

    files, missing = _collect_epl_files(targets)
    for target in missing:
        print(f"{_yellow('Skip:')} {target} not found")

    if not files:
        print(f"{_red('Error:')} No .epl files found.")
        return 1

    generator = DocGenerator()
    for filepath in files:
        generator.parse_file(str(filepath))

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if output_format in ('markdown', 'all'):
        (out_dir / 'api.md').write_text(generator.to_markdown(), encoding='utf-8')
        print(f'Generated: {out_dir}/api.md')
    if output_format in ('html', 'all'):
        (out_dir / 'api.html').write_text(generator.to_html(), encoding='utf-8')
        print(f'Generated: {out_dir}/api.html')
    if output_format in ('json', 'all'):
        (out_dir / 'api.json').write_text(generator.to_json(), encoding='utf-8')
        print(f'Generated: {out_dir}/api.json')

    total_entries = sum(len(module.entries) for module in generator.modules)
    print(f"\n  Documentation generated:")
    print(f"    {len(generator.modules)} modules, {total_entries} documented items")
    return 0


def _debug(args, flags):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1

    filename = args[0]
    breakpoint_specs = []
    i = 1
    while i < len(args):
        arg = args[i]
        if arg in ('-b', '--break') and i + 1 < len(args):
            breakpoint_specs.append(args[i + 1])
            i += 2
            continue
        print(f"{_red('Error:')} Unknown debug option: {arg}")
        return 1

    try:
        from epl.debugger import EPLDebugger, DebugInterpreter

        source = _read_epl_source(filename)
        _, program = _load_epl_program(filename)

        debugger = EPLDebugger()
        for bp in breakpoint_specs:
            try:
                debugger.state.add_breakpoint(line=int(bp))
            except ValueError:
                debugger.state.add_breakpoint(function_name=bp)

        debugger.state.source_file = filename
        debugger.state.source_lines = source.split('\n')

        interpreter = DebugInterpreter(debugger)

        print(f"  EPL Debugger — {filename}")
        print(f"  Breakpoints: {len(debugger.state.breakpoints)}")
        print("  Type 'help' for commands, 'c' to continue\n")
        interpreter.execute(program)
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        from epl.errors import EPLError

        if isinstance(exc, EPLError) and '--json' in flags:
            print(exc.to_json(), file=sys.stderr)
        else:
            print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _transpile_js(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1
    filename = args[0]
    try:
        from epl.js_transpiler import transpile_to_js

        _, program = _load_epl_program(filename)
        output_path = _write_generated_text(filename, '.js', transpile_to_js(program))
        print(f"  JavaScript written to: {output_path}")
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _transpile_node(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1
    filename = args[0]
    try:
        from epl.js_transpiler import transpile_to_node

        _, program = _load_epl_program(filename)
        output_path = _write_generated_text(filename, '.node.js', transpile_to_node(program))
        print(f"  Node.js written to: {output_path}")
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _transpile_kotlin(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1
    filename = args[0]
    try:
        from epl.kotlin_gen import transpile_to_kotlin

        _, program = _load_epl_program(filename)
        output_path = _write_generated_text(filename, '.kt', transpile_to_kotlin(program))
        print(f"  Kotlin written to: {output_path}")
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _transpile_python(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1
    filename = args[0]
    try:
        from epl.python_transpiler import transpile_to_python

        _, program = _load_epl_program(filename)
        output_path = _write_generated_text(filename, '.py', transpile_to_python(program))
        print(f"  Python written to: {output_path}")
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _android(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1
    filename = args[0]
    use_compose = '--compose' in args[1:]
    build_apk = '--build' in args[1:]
    app_name = None
    package_name = None

    rest = args[1:]
    i = 0
    while i < len(rest):
        if rest[i] == '--name' and i + 1 < len(rest):
            app_name = rest[i + 1]
            i += 2
            continue
        if rest[i] == '--package' and i + 1 < len(rest):
            package_name = rest[i + 1]
            i += 2
            continue
        i += 1

    try:
        from epl.kotlin_gen import generate_android_project

        _, program = _load_epl_program(filename)
        base = os.path.splitext(os.path.basename(filename))[0]
        output_dir = f'{base}_android'
        resolved_name = app_name or base.replace('_', ' ').title()
        generate_android_project(program, output_dir, app_name=resolved_name)

        print(f"\n  {_green('✓')} Android project generated: {_bold(output_dir)}/")
        print(f"  App name: {resolved_name}")
        if use_compose:
            print(f"  UI Mode: Jetpack Compose")

        if build_apk:
            _build_android_apk(output_dir)
        else:
            print(f"\n  {_dim('Next steps:')}")
            print(f"    1. Open in Android Studio: {output_dir}/")
            print(f"    2. Or build from CLI:  epl android {filename} --build")
            print(f"    3. The APK will be at: {output_dir}/app/build/outputs/apk/")
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _build_android_apk(project_dir):
    """Attempt to build APK using Gradle wrapper or system Gradle."""
    import subprocess as _sp
    import shutil

    # Find gradle/gradlew
    gradlew = os.path.join(project_dir, 'gradlew.bat' if os.name == 'nt' else 'gradlew')
    gradle_cmd = None

    if os.path.isfile(gradlew):
        gradle_cmd = gradlew
        if os.name != 'nt':
            os.chmod(gradlew, 0o755)
    elif shutil.which('gradle'):
        gradle_cmd = 'gradle'
    else:
        print(f"\n  {_yellow('⚠')} Gradle not found. Cannot build APK automatically.")
        print(f"  Install Gradle: https://gradle.org/install/")
        print(f"  Or open {project_dir}/ in Android Studio.")
        return

    # Check for ANDROID_HOME / ANDROID_SDK_ROOT
    sdk_root = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not sdk_root:
        # Try common locations
        candidates = [
            os.path.expanduser('~/Android/Sdk'),
            os.path.expanduser('~/Library/Android/sdk'),
            'C:\\Users\\' + os.environ.get('USERNAME', '') + '\\AppData\\Local\\Android\\Sdk',
        ]
        for c in candidates:
            if os.path.isdir(c):
                sdk_root = c
                break

    if not sdk_root:
        print(f"\n  {_yellow('⚠')} Android SDK not found (ANDROID_HOME not set).")
        print(f"  Install Android Studio or set ANDROID_HOME.")
        return

    print(f"\n  {_cyan('Building APK...')} (this may take a minute)")
    print(f"  SDK: {sdk_root}")

    env = os.environ.copy()
    env['ANDROID_HOME'] = sdk_root
    env['ANDROID_SDK_ROOT'] = sdk_root

    try:
        result = _sp.run(
            [gradle_cmd, 'assembleDebug'],
            cwd=project_dir,
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
        if result.returncode == 0:
            apk_path = os.path.join(project_dir, 'app', 'build', 'outputs', 'apk', 'debug', 'app-debug.apk')
            if os.path.isfile(apk_path):
                size_mb = os.path.getsize(apk_path) / (1024 * 1024)
                print(f"\n  {_green('✓')} APK built successfully!")
                print(f"  {_bold(apk_path)} ({size_mb:.1f} MB)")
            else:
                print(f"\n  {_green('✓')} Build completed. Check {project_dir}/app/build/outputs/")
        else:
            print(f"\n  {_red('✗')} Build failed.")
            # Show last 10 lines of stderr
            lines = result.stderr.strip().split('\n')
            for line in lines[-10:]:
                print(f"    {line}")
    except _sp.TimeoutExpired:
        print(f"\n  {_red('✗')} Build timed out (5 min limit).")
    except Exception as e:
        print(f"\n  {_red('✗')} Build error: {e}")


def _desktop(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1
    filename = args[0]
    app_name = None
    width = 900
    height = 700

    i = 1
    while i < len(args):
        arg = args[i]
        if arg == '--name' and i + 1 < len(args):
            app_name = args[i + 1]
            i += 2
            continue
        if arg == '--width' and i + 1 < len(args):
            width = int(args[i + 1])
            i += 2
            continue
        if arg == '--height' and i + 1 < len(args):
            height = int(args[i + 1])
            i += 2
            continue
        print(f"{_red('Error:')} Unknown desktop option: {arg}")
        return 1

    try:
        from epl.desktop import generate_desktop_project

        _, program = _load_epl_program(filename)
        base = os.path.splitext(os.path.basename(filename))[0]
        resolved_name = app_name or base.title().replace('_', '')
        output_dir = f'{base}_desktop'
        generate_desktop_project(program, output_dir, app_name=resolved_name, width=width, height=height)
        print(f"  Desktop project generated: {output_dir}/")
        print(f"  App: {resolved_name} ({width}x{height})")
        print(f"  Build: cd {output_dir} && ./gradlew run")
        print("  Package: ./gradlew packageMsi  (or packageDmg/packageDeb)")
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _web(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1
    filename = args[0]
    mode = 'js'
    app_name = None

    i = 1
    while i < len(args):
        arg = args[i]
        if arg == '--mode' and i + 1 < len(args):
            mode = args[i + 1]
            i += 2
            continue
        if arg == '--name' and i + 1 < len(args):
            app_name = args[i + 1]
            i += 2
            continue
        print(f"{_red('Error:')} Unknown web option: {arg}")
        return 1

    try:
        from epl.wasm_web import generate_web_project

        _, program = _load_epl_program(filename)
        base = os.path.splitext(os.path.basename(filename))[0]
        resolved_name = app_name or base.title().replace('_', '')
        output_dir = f'{base}_web'
        generate_web_project(program, output_dir, app_name=resolved_name, mode=mode)
        print(f"  Web project generated: {output_dir}/")
        print(f"  Mode: {mode}")
        if mode == 'js':
            print(f"  Run: python -m http.server 3000 --directory {output_dir}/public")
        elif mode == 'wasm':
            print(f"  Build: cd {output_dir} && ./build.sh")
            print(f"  Run: python -m http.server 3000 --directory {output_dir}/public")
        elif mode == 'kotlin_js':
            print(f"  Build: cd {output_dir} && ./gradlew jsBrowserDevelopmentRun")
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _gui(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1

    if len(args) > 1:
        print(f"{_red('Error:')} Unknown gui option: {args[1]}")
        return 1

    filename = args[0]
    try:
        from epl.gui import EPLWindow, gui_available
        from epl.interpreter import Interpreter

        if not gui_available():
            print(f"{_red('Error:')} GUI requires tkinter. Install Python with Tk support.", file=sys.stderr)
            return 1

        _, program = _load_epl_program(filename)
        interpreter = Interpreter()
        interpreter.global_env.define_variable('EPLWindow', EPLWindow)
        interpreter.execute(program)
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _show_ir(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1
    filename = args[0]
    try:
        from epl.compiler import Compiler

        _, program = _load_epl_program(filename)
        print(Compiler().get_ir(program))
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except ImportError:
        print(f"{_red('Error:')} llvmlite not installed.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _run_vm(args, flags):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1
    filename = args[0]
    try:
        from epl.vm import compile_and_run

        source = _read_epl_source(filename)
        print(f"  EPL Bytecode VM — {os.path.basename(filename)}")
        print()
        result = compile_and_run(source)
        if result.get('error'):
            print(f"\nVM Error: {result['error']}", file=sys.stderr)
            return 1
        for line in result.get('output', []):
            print(line)
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _wasm(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1
    filename = args[0]
    try:
        from epl.compiler import Compiler

        _, program = _load_epl_program(filename)
        base = os.path.splitext(os.path.basename(filename))[0]
        wasm_path = Compiler(source_filename=filename).compile_to_wasm(program, output_path=base)
        print(f"  WebAssembly compiled: {wasm_path}")
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except ImportError:
        print(f"{_red('Error:')} llvmlite not installed.", file=sys.stderr)
        print("Install it with: pip install llvmlite", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _micropython(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1
    filename = args[0]
    target = 'esp32'

    i = 1
    while i < len(args):
        arg = args[i]
        if arg == '--target' and i + 1 < len(args):
            target = args[i + 1]
            i += 2
            continue
        print(f"{_red('Error:')} Unknown micropython option: {arg}")
        return 1

    valid_targets = ('esp32', 'pico')
    if target not in valid_targets:
        print(f"{_red('Error:')} Unknown target '{target}'. Valid: {', '.join(valid_targets)}")
        return 1

    try:
        from epl.micropython_transpiler import transpile_to_micropython

        _, program = _load_epl_program(filename)
        rendered = transpile_to_micropython(program, target=target)
        output_path = os.path.splitext(os.path.basename(filename))[0] + f'_{target}_mpy.py'
        with open(output_path, 'w', encoding='utf-8') as handle:
            handle.write(rendered)
        print(f"  MicroPython written to: {output_path}")
        print(f"  Target: {target.upper()}")
        print(f"  Upload with: mpremote cp {output_path} :")
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _benchmark(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1

    filename = args[0]
    runs = 5
    warmup = 1
    i = 1
    while i < len(args):
        arg = args[i]
        if arg == '--runs' and i + 1 < len(args):
            runs = int(args[i + 1])
            i += 2
            continue
        if arg.startswith('--runs='):
            runs = int(arg.split('=', 1)[1])
            i += 1
            continue
        if arg == '--warmup' and i + 1 < len(args):
            warmup = int(args[i + 1])
            i += 2
            continue
        if arg.startswith('--warmup='):
            warmup = int(arg.split('=', 1)[1])
            i += 1
            continue
        print(f"{_red('Error:')} Unknown benchmark option: {arg}")
        return 1

    try:
        import time as _time
        from epl.interpreter import Interpreter
        from epl.lexer import Lexer
        from epl.parser import Parser
        from epl.errors import set_source_context
        from epl.vm import compile_and_run

        source = _read_epl_source(filename)
        print(f"  EPL Benchmark — {os.path.basename(filename)}")
        print(f"  Runs: {runs}, Warmup: {warmup}")
        print("  " + "=" * 50)

        vm_time = None
        try:
            for _ in range(warmup):
                compile_and_run(source)
            times = []
            instructions_total = 0
            for _ in range(runs):
                t0 = _time.perf_counter()
                result = compile_and_run(source)
                times.append(_time.perf_counter() - t0)
                instructions_total += result.get('instructions_executed', 0)
            vm_time = min(times)
            avg_time = sum(times) / len(times)
            avg_ips = instructions_total // runs if runs else 0
            print(f"  VM:          {vm_time:.4f}s best, {avg_time:.4f}s avg  ({avg_ips:,} instructions)")
        except Exception as exc:
            print(f"  VM:          FAILED ({exc})")

        interp_time = None
        try:
            set_source_context(source, filename)
            for _ in range(warmup):
                program = Parser(Lexer(source).tokenize()).parse()
                Interpreter().execute(program)
            times = []
            for _ in range(runs):
                t0 = _time.perf_counter()
                program = Parser(Lexer(source).tokenize()).parse()
                Interpreter().execute(program)
                times.append(_time.perf_counter() - t0)
            interp_time = min(times)
            avg_time = sum(times) / len(times)
            print(f"  Interpreter: {interp_time:.4f}s best, {avg_time:.4f}s avg")
        except Exception as exc:
            print(f"  Interpreter: FAILED ({exc})")

        if vm_time and interp_time:
            speedup = interp_time / vm_time if vm_time > 0 else float('inf')
            print(f"  Speedup:     {speedup:.1f}x (best of {runs})")
        print("  " + "=" * 50)
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _profile(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1

    filename = args[0]
    trace_file = None
    top_n = 20

    i = 1
    while i < len(args):
        arg = args[i]
        if arg == '--trace' and i + 1 < len(args):
            trace_file = args[i + 1]
            i += 2
            continue
        if arg == '--top' and i + 1 < len(args):
            top_n = int(args[i + 1])
            i += 2
            continue
        print(f"{_red('Error:')} Unknown profile option: {arg}")
        return 1

    try:
        import time as _time
        from epl.interpreter import Interpreter
        from epl.profiler import get_profiler

        source = _read_epl_source(filename)
        program = _parse_epl_program(source, filename)

        profiler = get_profiler()
        profiler.reset()
        profiler.enable()

        print(f"  EPL Profiler — {os.path.basename(filename)}")
        print()
        t0 = _time.perf_counter()
        interpreter = Interpreter()
        interpreter.execute(program)
        total_time = (_time.perf_counter() - t0) * 1000
        profiler.disable()

        for line in interpreter.output_lines:
            print(line)

        print()
        print(profiler.report())
        print(f"\n  Wall time: {total_time:.2f} ms")

        stats = profiler.get_stats()
        if stats:
            sorted_funcs = sorted(stats.items(), key=lambda item: item[1]['total_ms'], reverse=True)
            for index, (name, stat) in enumerate(sorted_funcs):
                if index >= top_n:
                    break
                pct = (stat['total_ms'] / total_time * 100) if total_time > 0 else 0
                if index == 0:
                    print(f"\n  Top {min(top_n, len(sorted_funcs))} hotspots:")
                print(f"    {pct:5.1f}%  {stat['total_ms']:8.2f}ms  {stat['calls']:>4}x  {name}")

        if trace_file:
            profiler.export_trace(trace_file)
            print(f"\n  Trace exported to: {trace_file}")
            print("  View at: chrome://tracing")
        return 0
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _bench(args, flags):
    from benchmarks.run_benchmarks import run_suite

    json_output = '--json' in flags or '--json' in args
    runs = 5
    warmup = 1

    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith('--runs='):
            runs = int(arg.split('=', 1)[1])
            i += 1
            continue
        if arg == '--runs' and i + 1 < len(args):
            runs = int(args[i + 1])
            i += 2
            continue
        if arg.startswith('--warmup='):
            warmup = int(arg.split('=', 1)[1])
            i += 1
            continue
        if arg == '--warmup' and i + 1 < len(args):
            warmup = int(args[i + 1])
            i += 2
            continue
        if arg == '--json':
            i += 1
            continue
        print(f"{_red('Error:')} Unknown bench option: {arg}")
        return 1

    run_suite(runs=runs, warmup=warmup, json_output=json_output)
    return 0


def _site(args):
    from epl.site_generator import generate_site

    source_dirs = list(args)
    output_dir = None
    if '--output' in source_dirs:
        idx = source_dirs.index('--output')
        if idx + 1 >= len(source_dirs):
            print(f"{_red('Error:')} Missing output directory after --output")
            return 1
        output_dir = source_dirs[idx + 1]
        source_dirs = source_dirs[:idx] + source_dirs[idx + 2:]

    if not source_dirs:
        source_dirs = None

    out_dir, page_count = generate_site(source_dirs, output_dir)
    print(f"Generated {page_count} pages in {out_dir}/")
    return 0


def _playground(args):
    from epl.playground import start_playground

    port = 8080
    i = 0
    while i < len(args):
        if args[i] == '--port' and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
            continue
        print(f"{_red('Error:')} Unknown playground option: {args[i]}")
        return 1

    start_playground(port=port)
    return 0


def _notebook(args):
    from epl.notebook import start_notebook

    port = 8888
    i = 0
    while i < len(args):
        if args[i] == '--port' and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
            continue
        print(f"{_red('Error:')} Unknown notebook option: {args[i]}")
        return 1

    start_notebook(port=port)
    return 0


def _blocks(args):
    from epl.block_editor import start_block_editor

    port = 8090
    i = 0
    while i < len(args):
        if args[i] == '--port' and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
            continue
        print(f"{_red('Error:')} Unknown blocks option: {args[i]}")
        return 1

    start_block_editor(port=port)
    return 0


def _copilot(args):
    from epl.copilot import generate_from_description, run_copilot_interactive, start_copilot_web

    if '--web' in args:
        port = 8095
        i = 0
        while i < len(args):
            if args[i] == '--web':
                i += 1
                continue
            if args[i] == '--port' and i + 1 < len(args):
                port = int(args[i + 1])
                i += 2
                continue
            print(f"{_red('Error:')} Unknown copilot option: {args[i]}")
            return 1
        start_copilot_web(port=port)
        return 0

    if args:
        print(generate_from_description(' '.join(args)))
        return 0

    run_copilot_interactive()
    return 0


def _start_lsp(args):
    from epl.lsp_server import EPLLanguageServer

    tcp_mode = '--tcp' in args
    port = 2087

    i = 0
    while i < len(args):
        if args[i] == '--port' and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
            continue
        i += 1

    server = EPLLanguageServer()
    if tcp_mode:
        print(f"  EPL Language Server starting on TCP port {port}...")
        print(f"  Connect your IDE to localhost:{port}")
        server.start_tcp(port)
    else:
        server.start_stdio()
    return 0


def _ai(args):
    return _legacy_dispatch(['ai'] + args)


def _ai_gen(args):
    return _legacy_dispatch(['gen'] + args)


def _ai_explain(args):
    return _legacy_dispatch(['explain'] + args)


def _package(args):
    args = _resolve_target_args(args)
    if not args:
        print(f"{_red('Error:')} No file specified.")
        return 1
    filename = args[0]
    mode = 'exe'
    output_dir = None

    i = 1
    while i < len(args):
        arg = args[i]
        if arg == '--mode' and i + 1 < len(args):
            mode = args[i + 1]
            i += 2
            continue
        if arg == '--output' and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
            continue
        print(f"{_red('Error:')} Unknown package option: {arg}")
        return 1

    try:
        from epl.packager import package

        result = package(os.path.abspath(filename), mode=mode, output_dir=output_dir)
        return 0 if result else 1
    except FileNotFoundError:
        print(f"{_red('Error:')} File not found: {filename}")
        return 1
    except Exception as exc:
        print(f"{_red('Error:')} {exc}", file=sys.stderr)
        return 1


def _cloud():
    return _legacy_dispatch(['cloud'])


def _train():
    return _legacy_dispatch(['train'])


def _model():
    return _legacy_dispatch(['model'])


# ─── Phase 7 Commands ────────────────────────────────────

def _resolve():
    from epl.resolver import resolve_from_manifest, print_resolution
    result = resolve_from_manifest()
    print_resolution(result)


def _workspace(args):
    from epl.workspace import workspace_cli
    workspace_cli(list(args))


def _ci(args):
    from epl.ci_gen import ci_cli
    ci_cli(list(args))


def _sync_index(args):
    from epl.package_index import PackageIndex
    idx = PackageIndex()
    force = '--force' in args
    if idx.sync_index(force=force):
        print("  Package index synced successfully.")
    else:
        print("  Failed to sync package index.")


def _list_modules():
    """List available EPL standard library modules."""
    import json
    registry_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stdlib', 'registry.json')
    try:
        with open(registry_path, 'r', encoding='utf-8') as f:
            registry = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"{_red('Error:')} stdlib registry not found.")
        return 1

    print(f"\n{_bold('EPL Standard Library Modules')}")
    print(_dim('Use: Import "name" to load a module') + "\n")
    for name, info in registry['modules'].items():
        print(f"  {_green(name):30s} {info['description']}")
    count = len(registry['modules'])
    print(f"\n{_dim(f'{count} modules available | EPL v{__version__}')}\n")
    return 0


# ─── Entry Point ──────────────────────────────────────────

def main():
    """CLI entry point for setuptools console_scripts."""
    sys.exit(cli_main())


if __name__ == '__main__':
    main()
