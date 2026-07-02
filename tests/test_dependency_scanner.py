"""Tests for packager.DependencyScanner import following (10.1.1).

The scanner bundles an entry `.epl` file's transitive local imports for native
packaging and the desktop WebView launcher. Historically it used a lowercase-only
regex (`import "..."`) that never matched EPL's capital `Import` keyword and that
also matched imports written inside comments/strings. It now extracts imports
from the parsed AST (so comments/strings are ignored) and resolves them
source-file-relative, mirroring the interpreter.

These tests pin the behavior CodeRabbit flagged:
  1. AST extraction — no false positives from `Import` inside a comment/string.
  2. The `Use "x"` string form is followed as a local import (it parses to the
     same ImportStatement as `Import "x"`), while `Use python "lib"` is not.
  3. Nested (source-file-relative) imports are found, cycles terminate.
  4. The regex fallback (for unparseable source) covers both forms.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.packager import DependencyScanner


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)


def test_extract_imports_ignores_comments_and_strings():
    """`Import`/`Use` inside a comment or string literal must NOT be treated
    as a real dependency (the whole point of parsing the AST)."""
    source = (
        'Note: Import "not_a_real_dep"\n'
        'Set message to "please Import \\"also_not_real\\" here"\n'
        'Import "genuine"\n'
    )
    imports = DependencyScanner._extract_imports(source)
    assert imports == ['genuine']


def test_extract_imports_capital_import_keyword():
    """EPL source uses the capital `Import` keyword; the old lowercase-only
    regex missed it entirely."""
    assert DependencyScanner._extract_imports('Import "utils"\n') == ['utils']


def test_extract_imports_use_string_form():
    """`Use "x"` parses to an ImportStatement (local import), so it must be
    followed; `Use python "lib"` is a foreign binding and must not be."""
    source = 'Use "helpers"\nUse python "math" as m\n'
    assert DependencyScanner._extract_imports(source) == ['helpers']


def test_scan_follows_nested_source_relative_imports(tmp_path):
    """A nested module importing a sibling resolves relative to the importing
    file, not the entry directory."""
    root = str(tmp_path)
    _write(os.path.join(root, 'main.epl'), 'Import "pkg/a"\nSay "hi"\n')
    _write(os.path.join(root, 'pkg', 'a.epl'), 'Import "b"\nSay "a"\n')
    _write(os.path.join(root, 'pkg', 'b.epl'), 'Say "b"\n')

    deps = DependencyScanner(os.path.join(root, 'main.epl')).scan()
    names = sorted(os.path.basename(d) for d in deps)
    assert names == ['a.epl', 'b.epl', 'main.epl']


def test_scan_terminates_on_import_cycle(tmp_path):
    """Mutually-importing files must not loop forever."""
    root = str(tmp_path)
    _write(os.path.join(root, 'x.epl'), 'Import "y"\nSay "x"\n')
    _write(os.path.join(root, 'y.epl'), 'Import "x"\nSay "y"\n')

    deps = DependencyScanner(os.path.join(root, 'x.epl')).scan()
    names = sorted(os.path.basename(d) for d in deps)
    assert names == ['x.epl', 'y.epl']


def test_scan_skips_missing_and_nonlocal_imports(tmp_path):
    """A non-local/stdlib import (no matching file) resolves to None and is
    simply not bundled — no crash."""
    root = str(tmp_path)
    _write(os.path.join(root, 'main.epl'), 'Import "math"\nImport "does_not_exist"\nSay "hi"\n')

    deps = DependencyScanner(os.path.join(root, 'main.epl')).scan()
    assert [os.path.basename(d) for d in deps] == ['main.epl']


def test_fallback_regex_covers_both_forms(monkeypatch):
    """When the source cannot be parsed, the fallback text scan still finds
    both `Import "x"` and `Use "x"` (case-insensitive)."""
    import epl.packager as packager

    class _Boom:
        def __init__(self, *a, **k):
            raise SyntaxError('unparseable')

    # Force the AST path to fail so the fallback runs.
    monkeypatch.setattr(packager, 'Lexer', _Boom, raising=False)
    source = 'Import "one"\nuse "two"\n'
    # _extract_imports imports Lexer locally, so patch at its import site:
    monkeypatch.setattr('epl.lexer.Lexer', _Boom)
    imports = DependencyScanner._extract_imports(source)
    assert sorted(imports) == ['one', 'two']
