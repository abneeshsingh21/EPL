"""Measure native-build coverage across examples vs the interpreter.

For each run-to-completion example, this:
  1. runs it under the interpreter (the reference output),
  2. attempts a native `epl build` + executes the binary,
  3. classifies the outcome.

Categories:
  pass      — native built, ran, output matches the interpreter
  refused   — safety gate declined to emit a binary (honest, not a crash)
  buildfail — compile/link failed (no binary)
  segfault  — binary ran but crashed (non-zero exit)
  mismatch  — binary ran cleanly but output differs from the interpreter

Servers / interactive / non-run examples are skipped. Deterministic-only:
programs using random/uuid/time are skipped (their output legitimately varies).

Run: python scripts/native_coverage.py [examples_glob]
"""

import glob
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Heuristic skips: these can't be compared as run-to-completion stdout.
_SKIP_SUBSTR = (
    'server',
    'webapp',
    'web_',
    'http',
    'route',
    'listen',
    'input(',
    'read_line',
    'ask(',
    'Start app',
    'Use python',
    'Use javascript',
)
_NONDET = ('random', 'uuid', 'time_now', 'now(', 'current_time')


def _clang():
    for c in (
        'clang',
        r'C:\Program Files\LLVM\bin\clang.exe',
        r'C:\Program Files (x86)\LLVM\bin\clang.exe',
    ):
        try:
            subprocess.run([c, '--version'], capture_output=True, timeout=15, check=True)
            return c
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
    return None


def classify(path, clang):
    with open(path, 'r', encoding='utf-8') as fh:
        src = fh.read()
    low = src.lower()
    if any(s.lower() in low for s in _SKIP_SUBSTR):
        return 'skip', 'server/interactive/ffi'
    if any(s in low for s in _NONDET):
        return 'skip', 'nondeterministic'

    env = dict(os.environ)
    env['PYTHONPATH'] = ROOT
    # Reference output from the interpreter.
    try:
        ref = subprocess.run(
            [sys.executable, '-m', 'epl', 'run', '--interpret', path],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            cwd=ROOT,
        )
    except subprocess.TimeoutExpired:
        return 'skip', 'interp-timeout'
    if ref.returncode != 0:
        return 'skip', 'interp-error'
    ref_out = ref.stdout.replace('\r\n', '\n')

    with tempfile.TemporaryDirectory() as td:
        prog = os.path.join(td, 'prog.epl')
        with open(prog, 'w', encoding='utf-8') as fh:
            fh.write(src)
        clang_dir = os.path.dirname(clang)
        if clang_dir and clang_dir not in env.get('PATH', ''):
            env['PATH'] = clang_dir + os.pathsep + env.get('PATH', '')
        build = subprocess.run(
            [sys.executable, '-m', 'epl', 'build', prog],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=td,
        )
        out_txt = (build.stdout + build.stderr).lower()
        if 'cannot guarantee a correct binary' in out_txt:
            return 'refused', ''
        exe = os.path.join(td, 'prog.exe')
        if not os.path.exists(exe):
            exe = os.path.join(td, 'prog')
        if not os.path.exists(exe):
            return 'buildfail', build.stderr.strip()[:120]
        try:
            run = subprocess.run([exe], capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return 'segfault', 'runtime-timeout'
        if run.returncode != 0:
            return 'segfault', f'exit {run.returncode}'
        got = (run.stdout or '').replace('\r\n', '\n')
        if got == ref_out:
            return 'pass', ''
        return 'mismatch', f'{ref_out[:40]!r} != {got[:40]!r}'


def main():
    clang = _clang()
    if not clang:
        print('no clang; cannot measure native coverage')
        return 1
    pattern = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'examples', '*.epl')
    files = sorted(glob.glob(pattern))
    counts = {}
    for path in files:
        cat, detail = classify(path, clang)
        counts[cat] = counts.get(cat, 0) + 1
        if cat not in ('skip',):
            print(f'  {cat:9} {os.path.basename(path):32} {detail}')
    print('\n=== counts ===')
    for k in ('pass', 'refused', 'mismatch', 'segfault', 'buildfail', 'skip'):
        if k in counts:
            print(f'  {k:9} {counts[k]}')
    measured = sum(v for k, v in counts.items() if k != 'skip')
    print(f'  measured  {measured}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
