"""Native-export portability analysis (v9.10.0).

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


@dataclass
class PortabilityReport:
    target: str  # 'android' | 'ios' | 'desktop'
    issues: list = field(default_factory=list)
    # Counts of portable top-level logic that DID survive, for an honest summary.
    portable_functions: int = 0
    portable_statements: int = 0

    @property
    def blocking(self) -> list:
        return [i for i in self.issues if i.blocking]

    @property
    def warnings(self) -> list:
        return [i for i in self.issues if not i.blocking]

    @property
    def has_blocking(self) -> bool:
        return any(i.blocking for i in self.issues)

    def add(self, line, construct, detail, blocking=True):
        self.issues.append(PortabilityIssue(line or 0, construct, detail, blocking))


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


def analyze(program: ast.Program, target: str, has_db_bridge: bool = True) -> PortabilityReport:
    """Build a portability report for `program` against `target`.

    `has_db_bridge` reflects whether the target's generated runtime now ships a
    `db_*` implementation (True since v9.10.0 for android/desktop). When True,
    database calls are portable and not flagged.
    """
    report = PortabilityReport(target=target)

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
        elif isinstance(node, (getattr(ast, 'StoreStatement', ()), getattr(ast, 'FetchStatement', ()))):
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
                    f'No database bridge in the {target} runtime; this call '
                    'will not compile.',
                )

    _walk(program, visit)

    for stmt in getattr(program, 'statements', []) or []:
        if isinstance(stmt, ast.FunctionDef):
            report.portable_functions += 1
        elif not _is_web_only_toplevel(stmt):
            report.portable_statements += 1

    return report


def _is_web_only_toplevel(stmt) -> bool:
    web_types = (
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
        lines.append(
            paint('green', f'  ✓ All constructs are portable to {report.target}.')
        )
        return '\n'.join(lines)

    lines.append('')
    if blocking:
        lines.append(
            paint(
                'red',
                f'  ⚠ {len(blocking)} construct(s) cannot be ported to '
                f'{report.target} natively:',
            )
        )
        for issue in blocking[:12]:
            lines.append(f'      • line {issue.line}: {issue.construct} — {issue.detail}')
        if len(blocking) > 12:
            lines.append(paint('dim', f'      … and {len(blocking) - 12} more (see PORTING_REPORT.md)'))
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
        out.append('✅ **Everything in this program is portable to '
                    f'{report.target}.** Nothing was dropped.')
        out.append('')
        return '\n'.join(out)

    if report.blocking:
        out.append('## Not ported (blocking)')
        out.append('')
        out.append('| Line | Construct | Why it was dropped |')
        out.append('|-----:|-----------|--------------------|')
        for i in report.blocking:
            out.append(f'| {i.line} | {i.construct} | {i.detail} |')
        out.append('')
    if report.warnings:
        out.append('## Warnings')
        out.append('')
        out.append('| Line | Construct | Note |')
        out.append('|-----:|-----------|------|')
        for i in report.warnings:
            out.append(f'| {i.line} | {i.construct} | {i.detail} |')
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
