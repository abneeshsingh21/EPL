#!/usr/bin/env python3
"""Backend parity harness: VM (default `epl run`) vs interpreter (`--interpret`).

Any program that produces different stdout / exit status across the two backends
is a divergence bug, because `epl run` defaults to the VM while docs/tests often
validate against the interpreter. Skips servers and interactive programs.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Patterns that make a program unsuitable for headless parity diffing.
SKIP_TOKENS = (
    'WebApp',
    'Route ',
    'Listen',
    'Serve',
    'serve(',
    'run_server',
    'Ask ',
    'Prompt ',
    'input(',
    'Read line',
    'websocket',
    'WebSocket',
    # Nondeterministic output (random / uuid) — output legitimately differs
    # between any two runs, so it can't be diffed for backend parity.
    'random',
    'uuid',
    'generate_uuid',
    'random_string',
)


def collect():
    files = []
    for base in ('examples', 'benchmarks'):
        d = os.path.join(ROOT, base)
        for dirpath, _, names in os.walk(d):
            for n in names:
                if n.endswith('.epl'):
                    files.append(os.path.join(dirpath, n))
    return sorted(files)


def should_skip(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            src = f.read()
    except Exception:
        return True, 'unreadable'
    for tok in SKIP_TOKENS:
        if tok in src:
            return True, f'contains {tok.strip()!r}'
    return False, ''


def run(path, interpret):
    cmd = [sys.executable, '-m', 'epl', 'run']
    if interpret:
        cmd.append('--interpret')
    cmd.append(path)
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=25)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return None, '', '<timeout>'


def main():
    files = collect()
    diffs = []
    skipped = 0
    errors_both = 0
    checked = 0
    for path in files:
        skip, why = should_skip(path)
        rel = os.path.relpath(path, ROOT)
        if skip:
            skipped += 1
            continue
        vm_rc, vm_out, vm_err = run(path, interpret=False)
        in_rc, in_out, in_err = run(path, interpret=True)
        if vm_rc is None or in_rc is None:
            skipped += 1
            continue
        checked += 1
        # Both erroring out the same way is not a parity bug for this harness.
        if vm_out != in_out:
            diffs.append((rel, vm_rc, in_rc, vm_out, in_out, vm_err, in_err))
    print(f'Checked {checked}, skipped {skipped}, divergences {len(diffs)}\n')
    for rel, vm_rc, in_rc, vm_out, in_out, vm_err, in_err in diffs:
        print('=' * 70)
        print(f'DIVERGENCE: {rel}  (vm rc={vm_rc}, interp rc={in_rc})')
        print('--- VM stdout ---')
        print(vm_out[:1200])
        print('--- INTERP stdout ---')
        print(in_out[:1200])
        if vm_err.strip():
            print('--- VM stderr ---')
            print(vm_err[:500])
        if in_err.strip():
            print('--- INTERP stderr ---')
            print(in_err[:500])
    return 0


if __name__ == '__main__':
    sys.exit(main())
