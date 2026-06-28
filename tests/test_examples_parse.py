"""Smoke test: every shipped example app must parse cleanly.

Guards against the omniapp finding that canonical examples ship broken
(`todo_app.epl` hit a runtime type error, `spark_board.epl` used `{id}` routes
that silently 404'd). Parsing all example apps on every CI run keeps the
flagship examples honest.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.lexer import Lexer
from epl.parser import Parser

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _REPO_ROOT / 'examples'
_APPS_DIR = _EXAMPLES_DIR / 'apps'


def _example_apps():
    return sorted(_APPS_DIR.glob('*.epl'))


# Files that legitimately do NOT parse with the *standard* grammar, each with a
# reason. Keyed by POSIX-style path relative to examples/. These are excluded
# from the recursive parse guard (but NOT from the per-folder runtime gate in
# test_starter_examples.py, which runs them the right way).
_PARSE_EXCLUSIONS = {
    # `Test "…" … End Test` assertion DSL — parsed by `epl test`, not `epl run`.
    'test_strings.epl': 'Test/expect DSL, run via `epl test`',
    # `Use javascript "…"` foreign-code bridge — needs the JS bridge enabled.
    'js_bridge_demo.epl': 'JavaScript bridge (Use javascript), needs Node runtime',
}


def _all_examples():
    """Every shipped ``.epl`` under examples/ — including the per-folder starters
    (``examples/<name>/main.epl``) that live outside the apps/ glob — except the
    documented special-mode files in ``_PARSE_EXCLUSIONS``."""
    out = []
    for path in sorted(_EXAMPLES_DIR.rglob('*.epl')):
        rel = path.relative_to(_EXAMPLES_DIR).as_posix()
        if rel in _PARSE_EXCLUSIONS:
            continue
        out.append(path)
    return out


class TestExampleAppsParse(unittest.TestCase):
    def test_apps_directory_present(self):
        self.assertTrue(_APPS_DIR.is_dir(), f'missing {_APPS_DIR}')
        self.assertTrue(_example_apps(), 'no .epl example apps found')

    def test_every_example_app_parses(self):
        failures = []
        for path in _example_apps():
            source = path.read_text(encoding='utf-8')
            try:
                Parser(Lexer(source).tokenize()).parse()
            except Exception as exc:  # noqa: BLE001 — collect all, report together
                failures.append(f'{path.name}: {exc}')
        self.assertFalse(failures, 'example apps failed to parse:\n' + '\n'.join(failures))

    def test_every_shipped_example_parses(self):
        """Recursive guard: NO example anywhere under examples/ may fail to parse.

        The per-folder starters (examples/<name>/main.epl) fell through both the
        apps/ glob here and the top-level glob in test_examples_run.py, which is
        how an AUTO-FIX pass shipped corrupted starters undetected."""
        failures = []
        for path in _all_examples():
            rel = path.relative_to(_REPO_ROOT)
            source = path.read_text(encoding='utf-8')
            try:
                Parser(Lexer(source).tokenize()).parse()
            except Exception as exc:  # noqa: BLE001 — collect all, report together
                failures.append(f'{rel}: {exc}')
        self.assertFalse(failures, 'examples failed to parse:\n' + '\n'.join(failures))


if __name__ == '__main__':
    unittest.main()
