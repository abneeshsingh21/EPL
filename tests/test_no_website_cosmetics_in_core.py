"""Guard: website-specific demo cosmetics must NOT live in the shared core.

v9.7.0 baked five website-only constructs into core (shipped to every PyPI
user): ``noise_overlay``, ``bg_noise``, ``words_pull_up`` and
``words_pull_up_multi_style`` — pure marketing cosmetics — plus their default
CSS and an unconditional ``IntersectionObserver`` script emitted on every page.

Those were removed. The flagship site reproduces them in its own layer (via the
``Raw HTML`` escape hatch + site-owned CSS/JS), proven byte-identical at build
time. ``store_list`` was deliberately KEPT: it is a legitimate data-store
feature (used by ``examples/todo.epl``, styled with core design tokens), not
site cosmetics — there is no in-page loop primitive to replace it.

These tests fail if any of the cosmetics creep back into core.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl import ast_nodes as ast
from epl.html_gen import generate_html
from epl.lexer import Lexer
from epl.parser import Parser
from epl.tokens import KEYWORDS, TokenType

REMOVED_KEYWORDS = ['wordspullup', 'wordspullupmultistyle', 'segment', 'noiseoverlay', 'bgnoise']
REMOVED_TOKENS = [
    'WORDS_PULL_UP',
    'WORDS_PULL_UP_MULTI_STYLE',
    'SEGMENT',
    'NOISE_OVERLAY',
    'BG_NOISE',
]


def _render_page(src):
    program = Parser(Lexer(src).tokenize()).parse()
    return generate_html(program.statements[0])


@pytest.mark.parametrize('kw', REMOVED_KEYWORDS)
def test_demo_keyword_removed_from_keyword_map(kw):
    assert kw not in KEYWORDS, f'website cosmetic keyword {kw!r} crept back into core'


@pytest.mark.parametrize('tok', REMOVED_TOKENS)
def test_demo_token_type_removed(tok):
    assert not hasattr(TokenType, tok), f'website cosmetic token {tok} crept back into core'


def test_default_page_has_no_demo_cosmetics():
    html = _render_page('Page "Home"\n    Heading "Hi"\nEnd')
    for needle in (
        'native-pull-up',
        'native-words-wrapper',
        'native-noise',
        'feTurbulence',
        "url('#noise')",
        "url('#bgNoise')",
    ):
        assert needle not in html, f'core default output still emits {needle!r}'


def test_no_unconditional_scroll_observer():
    # The pull-up scroll observer used to ship on every generated page.
    html = _render_page('Page "Home"\n    Heading "Hi"\nEnd')
    assert 'IntersectionObserver' not in html


def test_store_list_is_kept_and_renders():
    # store_list is a legitimate data-store feature — it must keep working.
    src = (
        'Create WebApp called todoApp\n'
        'Route "/" shows\n'
        '    Page "Home"\n'
        '        Say items from "tasks" delete "/delete"\n'
        '    End\n'
        'End\n'
    )
    program = Parser(Lexer(src).tokenize()).parse()
    route = next(n for n in program.statements if isinstance(n, ast.Route))
    page = next(s for s in route.body if isinstance(s, ast.PageDef))
    assert page.elements[0].tag == 'store_list'

    html = generate_html(page, data_store={'tasks': ['buy milk', 'walk dog']})
    assert 'buy milk' in html and 'walk dog' in html
    assert 'Delete' in html  # delete button still rendered
