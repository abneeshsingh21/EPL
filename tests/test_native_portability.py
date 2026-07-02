"""Tests for honest native-export portability analysis (v9.10.0).

The Android/iOS/desktop generators transliterate EPL logic to Kotlin/Swift and
historically dropped web-only constructs silently while still printing
"✓ generated". `epl.native_portability` walks the AST and reports — truthfully —
everything that could not be ported, so the build no longer lies about coverage.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.lexer import Lexer
from epl.native_portability import (
    analyze,
    render_console,
    render_markdown,
)
from epl.parser import Parser


def parse(source):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


WEB_APP = """\
Create WebApp called blogApp

Route "/" shows
    Page "Home"
        Heading "Hello"
    End
End

Start blogApp on port 4000
"""

PURE_LOGIC = """\
Function add takes a, b
    Return a plus b
End

Set total to 5
Display total
"""


def test_web_app_has_blocking_issues():
    report = analyze(parse(WEB_APP), 'android')
    assert report.has_blocking
    constructs = {i.construct for i in report.blocking}
    # The web server, the route, and the server start must all be flagged.
    assert 'WebApp' in constructs
    assert 'Route' in constructs
    assert 'Start server' in constructs


def test_route_issue_points_at_webview():
    report = analyze(parse(WEB_APP), 'ios')
    route = next(i for i in report.blocking if i.construct == 'Route')
    assert route.line > 0
    assert 'WebView' in route.detail or 'webview' in route.detail


def test_pure_logic_is_fully_portable():
    report = analyze(parse(PURE_LOGIC), 'desktop')
    assert not report.has_blocking
    assert report.issues == []
    assert report.portable_functions >= 1


def test_db_calls_flagged_without_bridge_only():
    source = 'Set rows to db_query("SELECT 1")\nDisplay rows\n'
    program = parse(source)
    flagged = analyze(program, 'android', has_db_bridge=False)
    assert any(i.construct.startswith('db_query') for i in flagged.blocking)
    # With a bridge present (the v9.10.0 default), the call is portable.
    ok = analyze(program, 'android', has_db_bridge=True)
    assert not any(i.construct.startswith('db_query') for i in ok.issues)


def test_cli_reports_db_portable_for_android_only(tmp_path):
    """The cli wires has_db_bridge per target: the android Kotlin runtime ships a
    real SQLite bridge (v10.0.1, H1), so db_* is portable there; ios/desktop have
    no verified bridge and must still report db_* as unportable."""
    from epl.cli import _emit_porting_report

    program = parse('Set rows to db_query("SELECT 1")\nDisplay rows\n')

    def db_flagged_for(target):
        out = tmp_path / target
        out.mkdir()
        _emit_porting_report(program, target, str(out))
        md = (out / 'PORTING_REPORT.md').read_text(encoding='utf-8')
        return 'db_query' in md

    assert not db_flagged_for('android'), 'android has the SQLite bridge — db_* is portable'
    assert db_flagged_for('ios'), 'ios has no db bridge — db_* must still be flagged'
    assert db_flagged_for('desktop'), 'desktop has no db bridge — db_* must still be flagged'


def test_target_is_recorded():
    for target in ('android', 'ios', 'desktop'):
        assert analyze(parse(PURE_LOGIC), target).target == target


def test_render_console_mentions_webview_for_web_app():
    out = render_console(analyze(parse(WEB_APP), 'android'))
    assert 'cannot be ported' in out
    assert 'WebView' in out


def test_render_console_clean_for_pure_logic():
    out = render_console(analyze(parse(PURE_LOGIC), 'desktop'))
    assert '✓' in out
    assert 'portable' in out


def test_render_markdown_lists_blocking_table():
    md = render_markdown(analyze(parse(WEB_APP), 'android'), app_name='blog')
    assert '# Porting report — blog → android' in md
    assert '## Not ported (blocking)' in md
    assert '--webview' in md
    # Every blocking issue should appear as a table row.
    assert md.count('\n|') >= 3


def test_render_markdown_clean_for_pure_logic():
    md = render_markdown(analyze(parse(PURE_LOGIC), 'desktop'))
    assert 'portable' in md
    assert 'Not ported' not in md


def _write(path, text):
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)


def test_analyze_follows_local_imports(tmp_path):
    """The unportable code usually lives one Import away: a simple entry file
    just calls into an imported module. The checker must open that module."""
    api = tmp_path / 'api.epl'
    _write(str(api), WEB_APP)
    entry = tmp_path / 'main.epl'
    _write(str(entry), 'Import "api"\nDisplay "ready"\n')

    # Without following imports (no entry_path), the web app is invisible.
    blind = analyze(parse(entry.read_text(encoding='utf-8')), 'android')
    assert not blind.has_blocking

    # Following the import graph surfaces the route/server hidden in api.epl.
    report = analyze(
        parse(entry.read_text(encoding='utf-8')), 'android', entry_path=str(entry)
    )
    assert report.has_blocking
    constructs = {i.construct for i in report.blocking}
    assert 'Route' in constructs
    assert 'Start server' in constructs
    # And every imported-file issue is tagged with the file it came from.
    route = next(i for i in report.blocking if i.construct == 'Route')
    assert route.source == 'api.epl'


def test_analyze_follows_nested_imports(tmp_path):
    """Imports resolve source-file-relative, so a module importing a sibling in
    its own directory must be followed too (the depth-2 case)."""
    pkg = tmp_path / 'pkg'
    pkg.mkdir()
    _write(str(pkg / 'db.epl'), 'Set rows to db_query("SELECT 1")\nDisplay rows\n')
    _write(str(pkg / 'api.epl'), 'Import "db"\nDisplay "api"\n')  # sibling import
    entry = tmp_path / 'main.epl'
    _write(str(entry), 'Import "pkg/api"\nDisplay "ready"\n')

    report = analyze(
        parse(entry.read_text(encoding='utf-8')),
        'ios',
        has_db_bridge=False,
        entry_path=str(entry),
    )
    db = next((i for i in report.blocking if i.construct.startswith('db_query')), None)
    assert db is not None, 'db_query two imports deep must be reported'
    assert db.source == os.path.join('pkg', 'db.epl')


def test_analyze_handles_import_cycles(tmp_path):
    """A ↔ B import cycle must not loop forever."""
    a = tmp_path / 'a.epl'
    b = tmp_path / 'b.epl'
    _write(str(a), 'Import "b"\n' + WEB_APP)
    _write(str(b), 'Import "a"\nDisplay "b"\n')
    report = analyze(parse(a.read_text(encoding='utf-8')), 'android', entry_path=str(a))
    assert report.has_blocking  # terminates and still finds the web app


def test_analyze_ignores_unresolvable_imports(tmp_path):
    """A `use`-style / package / stdlib import that isn't a local file is simply
    skipped — the checker stays scoped to the developer's own project."""
    entry = tmp_path / 'main.epl'
    _write(str(entry), 'Import "numpy"\nDisplay "ok"\n')
    report = analyze(parse(entry.read_text(encoding='utf-8')), 'desktop', entry_path=str(entry))
    assert not report.has_blocking


def test_render_markdown_shows_imported_file_location(tmp_path):
    api = tmp_path / 'api.epl'
    _write(str(api), WEB_APP)
    entry = tmp_path / 'main.epl'
    _write(str(entry), 'Import "api"\nDisplay "ready"\n')
    report = analyze(parse(entry.read_text(encoding='utf-8')), 'android', entry_path=str(entry))
    md = render_markdown(report, app_name='blog')
    assert 'api.epl:' in md  # location column carries the imported file


def test_console_color_hooks_are_applied():
    calls = {'red': 0}

    def red(text):
        calls['red'] += 1
        return text

    render_console(
        analyze(parse(WEB_APP), 'android'),
        color={'red': red},
    )
    assert calls['red'] >= 1
