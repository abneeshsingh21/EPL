"""Dev tool: fix `Set <name> to` used for a FIRST assignment in example files.

EPL's `Set` is reassignment-only by design (it errors on an undeclared name to
catch typos); `Create`/`=`/`Remember` declare. Several official-package examples
wrongly use `Set` for the first assignment of a variable. This rewrites only the
first `Set <bareword> to ...` of a name that hasn't been declared/assigned yet in
the same file into `<bareword> = ...`, leaving genuine reassignments untouched.

Conservative: only plain barewords (not `Set a[i] to`, not `Set a.b to`), and it
tracks names introduced by Create/=/Remember/For-each/function params/Set so a
later Set of the same name stays a reassignment.

Usage: python scripts/_fix_set_decls.py --apply <file>...   (omit --apply = dry run)
"""

from __future__ import annotations

import re
import sys

# `Set <name> to <rhs>`  — name is a single identifier (no [ ] or .)
_SET = re.compile(r'^(\s*)Set\s+([A-Za-z_]\w*)\s+to\s+(.*)$')
_CREATE = re.compile(r'^\s*Create\s+(?:\w+\s+named\s+)?([A-Za-z_]\w*)\s+(?:equal to|=)\s')
_ASSIGN = re.compile(r'^\s*([A-Za-z_]\w*)\s*=\s')
_REMEMBER = re.compile(r'^\s*Remember\s+([A-Za-z_]\w*)\s+as\s')
_FOREACH = re.compile(r'^\s*For\s+each\s+([A-Za-z_]\w*)\s+in\b')
_FUNC = re.compile(r'^\s*Function\s+\w+\s+takes\s+(.+)$')


def fix_text(text: str) -> tuple[str, int]:
    seen: set[str] = set()
    out: list[str] = []
    changes = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip('\n')
        m = _CREATE.match(body) or _REMEMBER.match(body) or _FOREACH.match(body)
        if m:
            seen.add(m.group(1))
            out.append(line)
            continue
        a = _ASSIGN.match(body)
        if a:
            seen.add(a.group(1))
            out.append(line)
            continue
        f = _FUNC.match(body)
        if f:
            for p in re.split(r'\s+and\s+|\s*,\s*', f.group(1).strip()):
                p = p.strip()
                if re.fullmatch(r'[A-Za-z_]\w*', p):
                    seen.add(p)
            out.append(line)
            continue
        s = _SET.match(body)
        if s:
            indent, name, rhs = s.group(1), s.group(2), s.group(3)
            if name not in seen:
                seen.add(name)
                nl = '\n' if line.endswith('\n') else ''
                out.append(f'{indent}{name} = {rhs}{nl}')
                changes += 1
                continue
            seen.add(name)
        out.append(line)
    return ''.join(out), changes


def main() -> int:
    args = sys.argv[1:]
    apply = '--apply' in args
    files = [a for a in args if a != '--apply']
    total = 0
    for path in files:
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        fixed, n = fix_text(text)
        if n:
            total += n
            print(f'{"FIX " if apply else "WOULD FIX "}{n:>2}  {path}')
            if apply:
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(fixed)
    print(f'--- {total} first-assignment Set(s) across {len(files)} files ---')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
