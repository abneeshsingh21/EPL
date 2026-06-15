"""Phase 3 native head/SEO tests: server-rendered meta, link, font, OpenGraph,
Twitter directives via a top-level `Head` block and per-`Page` overrides.

Mirrors the parse -> generate_html -> assert pattern of test_web_dsl_css.py.
All head tags must appear in the served HTML's <head> (server-rendered, no JS).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl import ast_nodes as ast
from epl.errors import ParserError
from epl.html_gen import generate_html
from epl.lexer import Lexer
from epl.parser import Parser

_PAGE = 'Page "Home"\n    Div class "hero"\n        Text "x"\n    End\nEnd\n'


def _render(src):
    """Parse a program, render its PageDef with collected head directives."""
    program = Parser(Lexer(src).tokenize()).parse()
    page = next(s for s in program.statements if isinstance(s, ast.PageDef))
    head = [d for s in program.statements if isinstance(s, ast.HeadDef) for d in s.directives]
    return generate_html(page, head=head)


def _head(body, page=_PAGE):
    return 'Head\n' + body + 'End\n' + page


def _head_section(html):
    """Return only the <head>...</head> slice of the rendered HTML."""
    return html.split('</head>')[0]


# ── Basic meta directives ────────────────────────────────────────────────────


def test_description_meta():
    html = _render(_head('    Description "A plain-English language."\n'))
    assert '<meta name="description" content="A plain-English language.">' in html


def test_keywords_author_meta():
    html = _render(_head('    Keywords "lang, compiler"\n    Author "Abneesh"\n'))
    assert '<meta name="keywords" content="lang, compiler">' in html
    assert '<meta name="author" content="Abneesh">' in html


def test_theme_color_meta():
    html = _render(_head('    ThemeColor "#FFFFFF"\n'))
    assert '<meta name="theme-color" content="#FFFFFF">' in html


def test_generic_meta_directive():
    html = _render(_head('    Meta "robots" "index,follow"\n'))
    assert '<meta name="robots" content="index,follow">' in html


# ── Links: canonical, favicon, generic ───────────────────────────────────────


def test_canonical_link():
    html = _render(_head('    Canonical "https://epl.dev/"\n'))
    assert '<link rel="canonical" href="https://epl.dev/">' in html


def test_favicon_auto_type():
    html = _render(_head('    Favicon "/favicon.png"\n'))
    assert '<link rel="icon" type="image/png" href="/favicon.png">' in html


def test_generic_link_directive():
    html = _render(_head('    Link rel "preload" href "/hero.webp" as "image"\n'))
    assert 'rel="preload"' in html
    assert 'href="/hero.webp"' in html
    assert 'as="image"' in html


# ── Fonts ────────────────────────────────────────────────────────────────────


def test_font_emits_preconnect_and_css2_url():
    html = _render(_head('    Font "Inter" weights "400;700"\n'))
    assert '<link rel="preconnect" href="https://fonts.googleapis.com">' in html
    assert 'href="https://fonts.gstatic.com" crossorigin' in html
    assert 'fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap' in html


def test_font_space_becomes_plus():
    html = _render(_head('    Font "JetBrains Mono" weights "400"\n'))
    assert 'family=JetBrains+Mono:wght@400' in html


def test_two_fonts_emit_preconnect_once():
    html = _render(_head('    Font "Inter" weights "400"\n    Font "Lora" weights "700"\n'))
    assert html.count('rel="preconnect" href="https://fonts.googleapis.com"') == 1
    assert 'family=Inter' in html
    assert 'family=Lora' in html


# ── OpenGraph / Twitter ──────────────────────────────────────────────────────


def test_opengraph_directive():
    html = _render(_head('    OpenGraph title "EPL" description "Write code." type "website"\n'))
    assert '<meta property="og:title" content="EPL">' in html
    assert '<meta property="og:description" content="Write code.">' in html
    assert '<meta property="og:type" content="website">' in html


def test_twitter_directive():
    html = _render(_head('    Twitter card "summary_large_image" title "EPL"\n'))
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert '<meta name="twitter:title" content="EPL">' in html


# ── Per-page overrides ───────────────────────────────────────────────────────


def test_per_page_description_overrides_site_wide():
    page = (
        'Page "Terms"\n'
        '    Description "Terms page description."\n'
        '    Div class "legal"\n        Text "x"\n    End\n'
        'End\n'
    )
    html = _render(_head('    Description "Site-wide description."\n', page=page))
    assert '<meta name="description" content="Terms page description.">' in html
    # Site-wide description is deduped out — only the page one remains.
    assert 'Site-wide description.' not in html


def test_per_page_adds_when_no_site_wide():
    page = (
        'Page "Terms"\n'
        '    Canonical "https://epl.dev/terms"\n'
        '    Div class "legal"\n        Text "x"\n    End\n'
        'End\n'
    )
    program = Parser(Lexer(page).tokenize()).parse()
    pg = next(s for s in program.statements if isinstance(s, ast.PageDef))
    html = generate_html(pg, head=[])
    assert '<link rel="canonical" href="https://epl.dev/terms">' in html


# ── Security ─────────────────────────────────────────────────────────────────


def test_javascript_favicon_neutralized():
    html = _render(_head('    Favicon "javascript:alert(1)"\n'))
    assert 'javascript:alert(1)' not in html


def test_javascript_canonical_neutralized():
    html = _render(_head('    Canonical "javascript:alert(1)"\n'))
    assert 'javascript:alert(1)' not in html


def test_content_is_escaped():
    html = _render(_head('    Description "<script>x</script>"\n'))
    assert '<script>x</script>' not in html
    assert '&lt;script&gt;' in html


def test_meta_name_rejects_http_equiv_injection():
    # A bogus meta name with quotes/spaces must be rejected at parse time.
    with pytest.raises(ParserError):
        _render(_head('    Meta "http-equiv\\" content=\\"x" "1"\n'))


def test_invalid_font_weights_rejected():
    with pytest.raises(ParserError):
        _render(_head('    Font "Inter" weights "abc"\n'))


# ── Regression: no Head block ────────────────────────────────────────────────


def test_no_head_still_renders_fixed_head():
    program = Parser(Lexer(_PAGE).tokenize()).parse()
    page = next(s for s in program.statements if isinstance(s, ast.PageDef))
    html = generate_html(page, head=[])
    head = _head_section(html)
    assert '<meta charset="UTF-8">' in head
    assert '<title>Home</title>' in head
    # No stray empty meta/link tags injected.
    assert 'name="description"' not in head


def test_body_link_still_anchor_not_head_link():
    # `Link "text" to "url"` in a Page body stays an anchor element.
    page = 'Page "Home"\n    Link "Docs" to "/docs"\nEnd\n'
    program = Parser(Lexer(page).tokenize()).parse()
    pg = next(s for s in program.statements if isinstance(s, ast.PageDef))
    assert pg.head_directives == []
    html = generate_html(pg, head=[])
    assert '<a href="/docs">Docs</a>' in html
