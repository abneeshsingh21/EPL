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
