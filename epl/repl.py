"""
EPL REPL with prompt_toolkit — rich syntax highlighting, auto-suggest,
persistent history, and smart multiline continuation.

Falls back to plain readline REPL if prompt_toolkit is not installed.
"""

from __future__ import annotations

# ── Keyword lists ──────────────────────────────────────────────────────────────
EPL_KEYWORDS = [
    'Create',
    'Set',
    'Print',
    'Display',
    'Say',
    'If',
    'Else',
    'Otherwise',
    'End',
    'While',
    'For',
    'Each',
    'Repeat',
    'Times',
    'Function',
    'Define',
    'Return',
    'Class',
    'Extends',
    'New',
    'Try',
    'Catch',
    'Finally',
    'Throw',
    'Match',
    'When',
    'Default',
    'Import',
    'From',
    'Module',
    'Export',
    'Async',
    'Await',
    'Yield',
    'Assert',
    'Constant',
    'Enum',
    'Interface',
    'Override',
    'Abstract',
    'Private',
    'Public',
    'Protected',
    'Static',
    'equal to',
    'is greater than',
    'is less than',
    'is not equal to',
    'not equal to',
    'greater than or equal to',
    'less than or equal to',
    'and',
    'or',
    'not',
    'true',
    'false',
    'nothing',
    'null',
    'takes',
    'returns',
    'with',
    'as',
    'in',
    'to',
    'be',
    'is',
]

EPL_BUILTINS = [
    'length',
    'append',
    'remove',
    'contains',
    'replace',
    'uppercase',
    'lowercase',
    'split',
    'join',
    'trim',
    'to_integer',
    'to_text',
    'to_decimal',
    'type_of',
    'read_file',
    'write_file',
    'file_exists',
    'random',
    'round',
    'floor',
    'ceil',
    'absolute',
    'max',
    'min',
    'sum',
    'sort',
    'reverse',
    'unique',
    'print',
    'keys',
    'values',
    'has_key',
    'http_get',
    'http_post',
    'db_open',
    'db_query',
    'db_execute',
    'json_parse',
    'json_stringify',
    'now',
    'today',
    'sleep',
    'hash_sha256',
    'uuid',
    'base64_encode',
    'base64_decode',
]

# ── Pygments lexer for EPL highlighting ───────────────────────────────────────
try:
    from pygments.lexer import RegexLexer, bygroups, words
    from pygments.token import (
        Comment,
        Keyword,
        Literal,
        Name,
        Number,
        Operator,
        Punctuation,
        String,
        Text,
    )

    class EPLLexer(RegexLexer):
        """Minimal Pygments lexer for EPL syntax highlighting."""

        name = 'EPL'
        aliases = ['epl']
        filenames = ['*.epl']

        tokens = {
            'root': [
                # Comments
                (r'#.*$', Comment.Single),
                (r'(Note:|note:).*$', Comment.Single),
                # Strings
                (r'"[^"\\]*(?:\\.[^"\\]*)*"', String.Double),
                (r"'[^'\\]*(?:\\.[^'\\]*)*'", String.Single),
                # Numbers
                (r'\b\d+\.\d+\b', Number.Float),
                (r'\b\d+\b', Number.Integer),
                # Keywords
                (words(tuple(EPL_KEYWORDS), suffix=r'\b'), Keyword),
                # Builtins
                (words(tuple(EPL_BUILTINS), suffix=r'\b'), Name.Builtin),
                # Identifiers
                (r'[a-zA-Z_][a-zA-Z0-9_]*', Name),
                # Operators
                (r'[+\-*/%<>=!&|^~]', Operator),
                # Punctuation
                (r'[(),\[\]{}.:;]', Punctuation),
                # Whitespace
                (r'\s+', Text),
            ],
        }

    _HAS_PYGMENTS = True
except ImportError:
    _HAS_PYGMENTS = False
    EPLLexer = None


# ── prompt_toolkit REPL ───────────────────────────────────────────────────────
def _build_prompt_toolkit_repl(
    run_source_fn, count_open_blocks_fn, handle_command_fn, interpreter, history, session_lines
):
    """Build and run REPL using prompt_toolkit for rich UX."""
    # History file
    import pathlib

    from prompt_toolkit import PromptSession, print_formatted_text
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.styles import Style

    hist_path = str(pathlib.Path.home() / '.epl_history')

    # Tab completer
    completer = WordCompleter(
        EPL_KEYWORDS + EPL_BUILTINS,
        ignore_case=True,
        sentence=False,
    )

    # Color style — dark terminal friendly
    style = Style.from_dict(
        {
            'prompt': 'ansibrightblue bold',
            'continuation': 'ansigray',
            'bottom-toolbar': 'bg:ansibrightblack ansiwhite',
        }
    )

    # Syntax highlighting (if pygments available)
    lexer_obj = None
    if _HAS_PYGMENTS and EPLLexer is not None:
        try:
            from prompt_toolkit.lexers import PygmentsLexer

            lexer_obj = PygmentsLexer(EPLLexer)
        except Exception:
            pass

    session = PromptSession(
        history=FileHistory(hist_path),
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
        lexer=lexer_obj,
        style=style,
        mouse_support=False,
        complete_while_typing=True,
    )

    from epl import __version__ as _VER

    _bar = '\u2501' * 55
    print_formatted_text(
        HTML(
            '\n<ansibrightblue>' + _bar + '</ansibrightblue>\n'
            '  <b>EPL</b> \u2013 English Programming Language  '
            '<ansiyellow>v' + _VER + '</ansiyellow>\n'
            '  Type EPL code and press <b>Enter</b>.\n'
            '  <ansicyan>.help</ansicyan> for commands \u00b7 '
            '<ansicyan>Tab</ansicyan> to complete \u00b7 '
            '<ansired>exit</ansired> to quit\n'
            '<ansibrightblue>' + _bar + '</ansibrightblue>\n'
        )
    )

    def _toolbar():
        return HTML(' <b>EPL REPL</b>  · .help · .vars · .history · exit ')

    while True:
        try:
            line = session.prompt(
                HTML('<prompt>EPL</prompt><ansibrightblue>❯</ansibrightblue> '),
                bottom_toolbar=_toolbar,
                rprompt=HTML(' <ansigray>v%s</ansigray> ' % _VER),
            )
        except KeyboardInterrupt:
            print('\n  (Use "exit" to quit, Ctrl+D to force exit)\n')
            continue
        except EOFError:
            print('\nGoodbye!')
            break

        line = line.strip()
        if not line:
            continue

        if line.lower() in ('exit', 'quit', 'exit.', 'quit.', 'bye'):
            print('Goodbye!')
            break

        if line.startswith('.'):
            handle_command_fn(line, history, session_lines, interpreter)
            continue

        # Multiline block accumulation
        source = line
        open_blocks = count_open_blocks_fn(source)

        while open_blocks > 0:
            try:
                cont = session.prompt(
                    HTML('<continuation>...  </continuation>'),
                )
            except (EOFError, KeyboardInterrupt):
                print('\n  Input cancelled.')
                source = ''
                break
            source += '\n' + cont
            open_blocks = count_open_blocks_fn(source)

        if source:
            history.append(source)
            session_lines.append(source)
            run_source_fn(source, interpreter, '<repl>')


def _build_readline_repl(
    run_source_fn, count_open_blocks_fn, handle_command_fn, interpreter, history, session_lines
):
    """Fallback plain readline REPL."""
    try:
        import readline
    except ImportError:
        try:
            import pyreadline3 as readline
        except ImportError:
            readline = None

    if readline:

        def _completer(text, state):
            all_words = EPL_KEYWORDS + EPL_BUILTINS
            matches = [w for w in all_words if w.lower().startswith(text.lower())]
            return matches[state] if state < len(matches) else None

        readline.set_completer(_completer)
        readline.parse_and_bind('tab: complete')
        import atexit
        import pathlib

        hist = str(pathlib.Path.home() / '.epl_history')
        try:
            readline.read_history_file(hist)
        except (FileNotFoundError, OSError):
            pass
        atexit.register(lambda: readline.write_history_file(hist))

    from epl import __version__ as _VER

    print('=' * 55)
    print(f'  EPL - English Programming Language v{_VER}')
    print('  Type EPL statements to execute them.')
    print('  Type ".help" for commands, "exit" to leave.')
    print('=' * 55)
    print()

    while True:
        try:
            line = input('EPL> ')
        except (EOFError, KeyboardInterrupt):
            print('\nGoodbye!')
            break

        line = line.strip()
        if not line:
            continue

        if line.lower() in ('exit', 'quit', 'exit.', 'quit.', 'bye'):
            print('Goodbye!')
            break

        if line.startswith('.'):
            handle_command_fn(line, history, session_lines, interpreter)
            continue

        source = line
        open_blocks = count_open_blocks_fn(source)

        while open_blocks > 0:
            try:
                cont = input('...  ')
            except (EOFError, KeyboardInterrupt):
                print('\n  Input cancelled.')
                source = ''
                break
            source += '\n' + cont
            open_blocks = count_open_blocks_fn(source)

        if source:
            history.append(source)
            session_lines.append(source)
            run_source_fn(source, interpreter, '<repl>')


def start_rich_repl(run_source_fn, count_open_blocks_fn, handle_command_fn, interpreter):
    """
    Start the enhanced EPL REPL.
    Tries prompt_toolkit first, falls back to readline.
    """
    history = []
    session_lines = []

    try:
        import prompt_toolkit  # noqa: F401

        _build_prompt_toolkit_repl(
            run_source_fn,
            count_open_blocks_fn,
            handle_command_fn,
            interpreter,
            history,
            session_lines,
        )
    except ImportError:
        _build_readline_repl(
            run_source_fn,
            count_open_blocks_fn,
            handle_command_fn,
            interpreter,
            history,
            session_lines,
        )
