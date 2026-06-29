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

# Conditional/loop block openers and closers. A first `Set` that lands inside one
# of these is NOT safe to turn into a declaration: the branch may not execute, so
# a `Set` on the alternate path would reference an undeclared name. (Function
# bodies are intentionally excluded — a first assignment there always runs.)
# Continuations (Else/Otherwise/Case/When) stay inside the already-open block and
# must NOT change the depth, or it would never return to 0.
_BRANCH_OPEN = re.compile(r'^\s*(If|While|For|Repeat|Match|Try)\b')
_BRANCH_CLOSE = re.compile(r'^\s*End(\s+(if|while|for|repeat|match|try))?\b', re.I)


def fix_text(text: str) -> tuple[str, int]:
    seen: set[str] = set()
    out: list[str] = []
    changes = 0
    branch_depth = 0  # >0 means we are inside a conditional/loop region
    for line in text.splitlines(keepends=True):
        body = line.rstrip('\n')
        # Track conditional/loop nesting so a first `Set` inside a branch is left
        # untouched (fail closed) rather than rewritten to a path-dependent decl.
        if _BRANCH_CLOSE.match(body):
            branch_depth = max(0, branch_depth - 1)
        elif _BRANCH_OPEN.match(body):
            branch_depth += 1
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
                # Fail closed: only a first `Set` at function/module top level is
                # safe to turn into a declaration. Inside a branch it may not run.
                if branch_depth == 0:
                    seen.add(name)
                    nl = '\n' if line.endswith('\n') else ''
                    out.append(f'{indent}{name} = {rhs}{nl}')
                    changes += 1
                    continue
                # else: leave the Set as-is; mark seen so later Sets aren't touched
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
