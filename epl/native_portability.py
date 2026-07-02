"""Native-export portability analysis (v10.0.0).

The Android/iOS/desktop generators transliterate EPL logic to Kotlin/Swift.
Some EPL constructs have NO native equivalent in that model:

  * web routing/serving (`Route`, `WebApp`, `Start ... on port`, `Send`,
    `Redirect`, `web_request_*`) — there is no HTTP server in a native app,
  * web-only escape hatches (`Raw HTML`, `Script`, `Stylesheet`) — these are
    literal HTML/CSS/JS and cannot become native widgets,
  * server-side persistence helpers when the target runtime lacks a bridge.

Historically the generators silently dropped all of the above, exited 0, and
printed "✓ generated" — giving the false impression that the whole app had
been ported when ~90 % of it was discarded (omniapp findings H2/E2/F1/G1).

This module walks the AST ONCE and produces an honest `PortabilityReport`:
every unportable construct, with line number and reason. Callers render it to
the console (loud warning) and to `PORTING_REPORT.md`, and may treat blockers
as a hard error under `--strict`. It changes no codegen behavior — it only
tells the truth about what survived the port.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from epl import ast_nodes as ast

# Web request/runtime builtins that have no meaning in a native (non-server)
# app. A call to any of these from transpiled logic cannot work natively.
WEB_ONLY_BUILTINS = frozenset(
    {
        'web_request_data',
        'web_request_args',
        'web_request_method',
        'web_request_path',
        'web_request_header',
        'web_request_param',
        'web_request_files',
        'web_set_cors',
        'web_cookie_get',
        'web_cookie_set',
        'start_server',
        'serve',
    }
)


@dataclass
class PortabilityIssue:
    line: int
    construct: str  # short label, e.g. 'Route', 'Raw HTML'
    detail: str  # human-readable reason
    blocking: bool  # True = app cannot be a faithful native port
    source: str = ''  # imported file (relative to entry) the issue lives in; '' = entry file


@dataclass
class PortabilityReport:
    target: str  # 'android' | 'ios' | 'desktop'
    issues: list = field(default_factory=list)
    # Counts of portable top-level logic that DID survive, for an honest summary.
    portable_functions: int = 0
    portable_statements: int = 0
    # Internal: the file `analyze()` is currently walking as it follows the
    # import graph. `_current_rel` (path relative to the entry) is stamped onto
    # each issue via add(); `_current_file` anchors source-relative resolution
    # of nested imports. Not part of the public report shape.
    _current_file: 'str | None' = field(default=None, repr=False, compare=False)
    _current_rel: str = field(default='', repr=False, compare=False)

    @property
    def blocking(self) -> list:
        return [i for i in self.issues if i.blocking]

    @property
    def warnings(self) -> list:
        return [i for i in self.issues if not i.blocking]

    @property
    def has_blocking(self) -> bool:
        return any(i.blocking for i in self.issues)

    def add(self, line, construct, detail, blocking=True, source=None):
        # `source` defaults to whichever file the analyzer is currently walking
        # (set on the report during import recursion) so issues carry their file.
        if source is None:
            source = self._current_rel
        self.issues.append(PortabilityIssue(line or 0, construct, detail, blocking, source))


def _walk(node, visit):
    """Depth-first visit every ASTNode reachable from `node`."""
    if isinstance(node, ast.ASTNode):
        visit(node)
        for value in vars(node).values():
            _walk(value, visit)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _walk(item, visit)
    elif isinstance(node, dict):
        for item in node.values():
            _walk(item, visit)


# Web-only HtmlElement tags that are literal markup, not native widgets.
_RAW_TAGS = {
    'raw_html': 'Raw HTML',
    'script': 'Script',
    'stylesheet': 'Stylesheet',
}


def _resolve_local_import(filepath: str, current_file, entry_dir):
    """Resolve an `Import "..."` target to an on-disk local .epl file, or None.

    Mirrors the interpreter's *source-file-relative* resolution
    (interpreter._resolve_import_path): try relative to the importing file first,
    then the entry dir, then as an absolute/cwd path. Only real files are
    returned — native modules, the stdlib, and installed packages resolve to
    None so the checker stays scoped to the developer's own project and never
    triggers a package auto-install just to analyze.
    """
    if not filepath:
        return None
    candidates = []

    def add_candidate(path):
        candidates.append(path)
        if not path.endswith('.epl'):
            candidates.append(path + '.epl')

    if current_file:
        add_candidate(os.path.join(os.path.dirname(current_file), filepath))
    if entry_dir:
        add_candidate(os.path.join(entry_dir, filepath))
    add_candidate(filepath)

    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def _rel_label(abs_path, entry_dir):
    """Path shown in issues/reports: relative to the entry dir when possible."""
    if not abs_path:
        return ''
    if entry_dir:
        try:
            return os.path.relpath(abs_path, entry_dir)
        except ValueError:  # e.g. different drive on Windows
            pass
    return os.path.basename(abs_path)


def analyze(
    program: ast.Program,
    target: str,
    has_db_bridge: bool = True,
    entry_path: str | None = None,
) -> PortabilityReport:
    """Build a portability report for `program` against `target`.

    `has_db_bridge` reflects whether the target's generated runtime now ships a
    `db_*` implementation (True since v10.0.0 for android/desktop). When True,
    database calls are portable and not flagged.

    `entry_path` is the path of the file `program` was parsed from. When given,
    the analyzer follows the project's own `Import` graph: every local `.epl`
    file reached via `Import` is parsed and analyzed too, so unportable
    constructs living one function-call away in an imported module are reported
    instead of silently passing as "✓ portable" (omniapp finding: the guarantee
    used to hold only for single-file programs). Without `entry_path`, behavior
    is unchanged (entry file only) — keeping the older call signature working.
    """
    report = PortabilityReport(target=target)
    entry_abs = os.path.abspath(entry_path) if entry_path else None
    entry_dir = os.path.dirname(entry_abs) if entry_abs else None
    report._current_file = entry_abs
    report._current_rel = ''
    visited = {entry_abs} if entry_abs else set()

    def visit(node):
        if isinstance(node, ast.Route):
            report.add(
                node.line,
                'Route',
                f'HTTP route "{node.path}" — a native app has no web server; '
                'this route and its handler are not ported. Use the WebView '
                'target (`--webview`) to ship the real web app.',
            )
        elif isinstance(node, ast.WebApp):
            report.add(node.line, 'WebApp', 'Web server app — no native equivalent.')
        elif isinstance(node, ast.StartServer):
            report.add(
                node.line,
                'Start server',
                'Starting an HTTP server has no meaning in a native app.',
            )
        elif isinstance(node, ast.SendResponse):
            kind = getattr(node, 'response_type', '?')
            report.add(
                node.line,
                f'Send {kind}',
                'HTTP response — only valid inside a web route; dropped natively.',
            )
        elif isinstance(node, ast.ScriptBlock):
            report.add(
                node.line,
                'Script',
                'Client-side JavaScript cannot run as a native widget.',
            )
        elif isinstance(node, getattr(ast, 'RawStylesheet', ())):
            report.add(
                node.line,
                'Stylesheet',
                'Raw CSS has no native-widget equivalent; styling is not ported.',
            )
        elif isinstance(
            node, (getattr(ast, 'StoreStatement', ()), getattr(ast, 'FetchStatement', ()))
        ):
            report.add(
                node.line,
                'Store/Fetch',
                'Server-side collection storage has no native bridge; not ported.',
            )
        elif isinstance(node, ast.HtmlElement):
            label = _RAW_TAGS.get((node.tag or '').lower())
            if label:
                report.add(
                    node.line,
                    label,
                    f'`{label}` is literal web markup — it cannot become a '
                    'native widget and is dropped from the native UI.',
                )
        elif isinstance(node, ast.FunctionCall):
            name = getattr(node, 'name', None)
            if name in WEB_ONLY_BUILTINS:
                report.add(
                    node.line,
                    f'{name}()',
                    'Web-server builtin — undefined in a native runtime.',
                )
            elif name and name.startswith('db_') and not has_db_bridge:
                report.add(
                    node.line,
                    f'{name}()',
                    f'No database bridge in the {target} runtime; this call will not compile.',
                )
        # Follow the project's own import graph: an imported module's body is
        # where the unportable code usually lives (a simple entry file just
        # calls into it). Only followed when we know the entry path.
        if isinstance(node, ast.ImportStatement) and entry_dir is not None:
            _follow_import(node)

    def _follow_import(node):
        resolved = _resolve_local_import(node.filepath, report._current_file, entry_dir)
        if not resolved or resolved in visited:
            return  # non-local (native/stdlib/package), missing, or already seen
        visited.add(resolved)
        rel = _rel_label(resolved, entry_dir)
        try:
            from epl.lexer import Lexer
            from epl.parser import Parser

            with open(resolved, encoding='utf-8') as fh:
                imported = Parser(Lexer(fh.read()).tokenize()).parse()
        except Exception:
            report.add(
                node.line,
                'Import',
                f'Imported file "{node.filepath}" could not be parsed, so its '
                'constructs were not checked — treat its portability as unknown.',
                blocking=False,
            )
            return
        _analyze_file(imported, resolved, rel)

    def _analyze_file(prog, abs_path, rel):
        prev_file, prev_rel = report._current_file, report._current_rel
        report._current_file, report._current_rel = abs_path, rel
        _walk(prog, visit)
        for stmt in getattr(prog, 'statements', []) or []:
            if isinstance(stmt, ast.FunctionDef):
                report.portable_functions += 1
            elif not _is_web_only_toplevel(stmt):
                report.portable_statements += 1
        report._current_file, report._current_rel = prev_file, prev_rel

    _analyze_file(program, entry_abs, '')

    return report


def _is_web_only_toplevel(stmt) -> bool:
    web_types: tuple[type, ...] = (
        ast.Route,
        ast.WebApp,
        ast.StartServer,
        ast.SendResponse,
        ast.ScriptBlock,
    )
    raw_stylesheet = getattr(ast, 'RawStylesheet', None)
    if raw_stylesheet:
        web_types = web_types + (raw_stylesheet,)
    return isinstance(stmt, web_types)


def render_console(report: PortabilityReport, color=None) -> str:
    """Render a short, honest summary for stderr. `color` is an optional dict
    of ANSI helpers {'red','yellow','green','dim','bold'}; plain text if None."""
    c = color or {}

    def paint(key, text):
        fn = c.get(key)
        return fn(text) if fn else text

    lines = []
    blocking = report.blocking
    warnings = report.warnings
    if not report.issues:
        lines.append(paint('green', f'  ✓ All constructs are portable to {report.target}.'))
        return '\n'.join(lines)

    lines.append('')
    if blocking:
        lines.append(
            paint(
                'red',
                f'  ⚠ {len(blocking)} construct(s) cannot be ported to {report.target} natively:',
            )
        )
        for issue in blocking[:12]:
            where = f'{issue.source} line {issue.line}' if issue.source else f'line {issue.line}'
            lines.append(f'      • {where}: {issue.construct} — {issue.detail}')
        if len(blocking) > 12:
            lines.append(
                paint('dim', f'      … and {len(blocking) - 12} more (see PORTING_REPORT.md)')
            )
    if warnings:
        lines.append(paint('yellow', f'  ⚠ {len(warnings)} warning(s) — see PORTING_REPORT.md.'))
    lines.append('')
    lines.append(
        paint(
            'dim',
            f'  Ported: {report.portable_functions} function(s), '
            f'{report.portable_statements} top-level statement(s). '
            'For a faithful port of a web app, use the WebView target.',
        )
    )
    return '\n'.join(lines)


def render_markdown(report: PortabilityReport, app_name: str = 'App') -> str:
    """Render the full PORTING_REPORT.md content."""
    out = [
        f'# Porting report — {app_name} → {report.target}',
        '',
        'This file is generated by `epl ' + report.target + '`. It lists every '
        'EPL construct that **could not** be ported to a native '
        f'{report.target} app, so you know exactly what is missing instead of '
        'assuming the whole app was ported.',
        '',
        '## Summary',
        '',
        f'- Portable functions ported: **{report.portable_functions}**',
        f'- Portable top-level statements: **{report.portable_statements}**',
        f'- Blocking (not ported): **{len(report.blocking)}**',
        f'- Warnings: **{len(report.warnings)}**',
        '',
    ]
    if not report.issues:
        out.append(
            '✅ **Everything in this program is portable to '
            f'{report.target}.** Nothing was dropped.'
        )
        out.append('')
        return '\n'.join(out)

    def _loc(i):
        return f'{i.source}:{i.line}' if i.source else str(i.line)

    if report.blocking:
        out.append('## Not ported (blocking)')
        out.append('')
        out.append('| Location | Construct | Why it was dropped |')
        out.append('|----------|-----------|--------------------|')
        for i in report.blocking:
            out.append(f'| {_loc(i)} | {i.construct} | {i.detail} |')
        out.append('')
    if report.warnings:
        out.append('## Warnings')
        out.append('')
        out.append('| Location | Construct | Note |')
        out.append('|----------|-----------|------|')
        for i in report.warnings:
            out.append(f'| {_loc(i)} | {i.construct} | {i.detail} |')
        out.append('')

    out.append('## How to ship the full app natively')
    out.append('')
    out.append(
        'EPL web apps rely on HTTP routing, a Python/SQLite backend, and web '
        'escape hatches (`Raw HTML` / `Script` / `Stylesheet`). Those cannot be '
        'transliterated into native widgets. To ship the **real** app on '
        f'{report.target}, generate a WebView shell instead:'
    )
    out.append('')
    out.append('```')
    out.append(f'epl {report.target} <file.epl> --webview')
    out.append('```')
    out.append('')
    out.append(
        'The WebView target bundles your EPL web app and runs it inside a native '
        'shell, so the UI and backend are exactly what you built for the web. '
        'The transliterating target (this report) is best for **pure-logic** EPL '
        '(functions, math, data) with no web layer.'
    )
    out.append('')
    return '\n'.join(out)
