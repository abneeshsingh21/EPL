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
_APPS_DIR = _REPO_ROOT / 'examples' / 'apps'


def _example_apps():
    return sorted(_APPS_DIR.glob('*.epl'))


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


if __name__ == '__main__':
    unittest.main()
