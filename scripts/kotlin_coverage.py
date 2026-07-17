"""Differential coverage for the Kotlin transpiler: interpreter vs compiled JVM.

For each run-to-completion example, this:
  1. runs it under the interpreter (the reference output),
  2. transpiles it with `epl kotlin` (console `main()` form),
  3. compiles the Kotlin with a real kotlinc and runs it on the JVM,
  4. compares stdout against the interpreter.

Categories mirror scripts/native_coverage.py so the two read alike:
  pass       — compiled, ran, output matches the interpreter
  transpfail — `epl kotlin` refused/failed to emit Kotlin
  buildfail  — kotlinc rejected the emitted Kotlin (codegen bug)
  runfail    — class ran but crashed (non-zero exit / exception)
  mismatch   — ran cleanly but output differs from the interpreter

Servers / interactive / non-run / ffi examples are skipped, as are
nondeterministic programs (random/uuid/time) whose output legitimately varies.

The Kotlin toolchain is discovered from the Gradle cache (kotlin-compiler-
embeddable + stdlib, resolved by glob, no hardcoded hashes). If no toolchain is
found the run reports that and exits without failing CI.

Run: python scripts/kotlin_coverage.py [examples_glob ...]
"""

import glob
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


def _gradle_home():
    return os.environ.get('GRADLE_USER_HOME') or os.path.join(
        os.path.expanduser('~'), '.gradle'
    )


def _find_jar(module, prefer_version=None):
    """Newest matching jar for a Kotlin gradle module, ignoring sources/javadoc.

    When prefer_version is given, a jar of that exact version wins so the
    stdlib matches the compiler (mixing majors triggers metadata warnings)."""
    base = os.path.join(
        _gradle_home(),
        'caches',
        'modules-2',
        'files-2.1',
        'org.jetbrains.kotlin',
        module,
    )
    hits = [
        p
        for p in glob.glob(os.path.join(base, '*', '*', f'{module}-*.jar'))
        if 'sources' not in p and 'javadoc' not in p
    ]
    if prefer_version:
        exact = [p for p in hits if os.sep + prefer_version + os.sep in p]
        if exact:
            return sorted(exact)[-1]
    # Sort by version segment so the newest is last.
    hits.sort(key=lambda p: p.split(os.sep))
    return hits[-1] if hits else None


def _find_dep_jar(group, module):
    base = os.path.join(
        _gradle_home(), 'caches', 'modules-2', 'files-2.1', group, module
    )
    hits = [
        p
        for p in glob.glob(os.path.join(base, '*', '*', f'{module}-*.jar'))
        if 'sources' not in p and 'javadoc' not in p
    ]
    return sorted(hits)[-1] if hits else None


def discover_toolchain():
    """Resolve (compiler_classpath, stdlib_jar) or (None, None) if unavailable."""
    compiler = _find_jar('kotlin-compiler-embeddable')
    if not compiler:
        return None, None
    ver = None
    m = re.search(r'kotlin-compiler-embeddable-([\d.]+)\.jar$', compiler)
    if m:
        ver = m.group(1)
    stdlib = _find_jar('kotlin-stdlib', prefer_version=ver)
    if not stdlib:
        return None, None
    parts = [compiler, stdlib]
    for module in ('kotlin-script-runtime', 'kotlin-reflect'):
        j = _find_jar(module, prefer_version=ver)
        if j:
            parts.append(j)
    trove = _find_dep_jar('org.jetbrains.intellij.deps', 'trove4j')
    if trove:
        parts.append(trove)
    # The embeddable compiler references @NotNull at IR-lowering time but does
    # not bundle it; without this jar every compile dies with NoClassDefFoundError.
    annotations = _find_dep_jar('org.jetbrains', 'annotations')
    if annotations:
        parts.append(annotations)
    return os.pathsep.join(parts), stdlib


def _java():
    for j in ('java', os.path.join(os.environ.get('JAVA_HOME', ''), 'bin', 'java')):
        try:
            subprocess.run([j, '-version'], capture_output=True, timeout=15, check=True)
            return j
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            continue
    return None


def _main_class(kt_src):
    """Package-qualified JVM main class kotlinc emits for a file named prog.kt."""
    pkg = ''
    m = re.search(r'^\s*package\s+([\w.]+)', kt_src, re.MULTILINE)
    if m:
        pkg = m.group(1) + '.'
    return f'{pkg}ProgKt'


def classify(path, compiler_cp, stdlib, java):
    with open(path, 'r', encoding='utf-8') as fh:
        src = fh.read()
    low = src.lower()
    if any(s.lower() in low for s in _SKIP_SUBSTR):
        return 'skip', 'server/interactive/ffi'
    if any(s in low for s in _NONDET):
        return 'skip', 'nondeterministic'

    env = dict(os.environ)
    env['PYTHONPATH'] = ROOT
    # Compare both sides in UTF-8: Windows consoles default to legacy codepages
    # that mangle non-ASCII output (═, →) differently per process.
    env['PYTHONIOENCODING'] = 'utf-8'
    try:
        ref = subprocess.run(
            [sys.executable, '-m', 'epl', 'run', '--interpret', path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
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
        kt = os.path.join(td, 'prog.kt')
        try:
            tr = subprocess.run(
                [sys.executable, '-m', 'epl', 'kotlin', prog, '-o', kt],
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
                cwd=ROOT,
            )
        except subprocess.TimeoutExpired:
            return 'transpfail', 'transpile-timeout'
        if tr.returncode != 0 or not os.path.exists(kt):
            return 'transpfail', (tr.stdout + tr.stderr).strip()[:120]
        with open(kt, 'r', encoding='utf-8') as fh:
            kt_src = fh.read()

        out_dir = os.path.join(td, 'out')
        os.makedirs(out_dir, exist_ok=True)
        try:
            build = subprocess.run(
                [
                    java,
                    '-cp',
                    compiler_cp,
                    'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler',
                    kt,
                    '-classpath',
                    stdlib,
                    '-d',
                    out_dir,
                ],
                capture_output=True,
                text=True,
                timeout=180,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return 'buildfail', 'kotlinc-timeout'
        errs = [
            ln
            for ln in (build.stdout + build.stderr).splitlines()
            if ': error:' in ln.lower()
        ]
        if errs:
            return 'buildfail', errs[0].strip()[:120]
        if not glob.glob(os.path.join(out_dir, '**', '*.class'), recursive=True):
            return 'buildfail', (build.stdout + build.stderr).strip()[:120]

        try:
            run = subprocess.run(
                [
                    java,
                    # Java 17 on Windows defaults stdout to the ANSI codepage,
                    # mangling Unicode (box-drawing, ═) the interpreter emits fine.
                    '-Dfile.encoding=UTF-8',
                    '-cp',
                    out_dir + os.pathsep + stdlib,
                    _main_class(kt_src),
                ],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return 'runfail', 'runtime-timeout'
        if run.returncode != 0:
            return 'runfail', (run.stderr or '').strip().splitlines()[-1:][0][:120] if run.stderr.strip() else f'exit {run.returncode}'
        got = (run.stdout or '').replace('\r\n', '\n')
        if got == ref_out:
            return 'pass', ''
        return 'mismatch', f'{ref_out[:40]!r} != {got[:40]!r}'


def main():
    java = _java()
    if not java:
        print('no java; cannot run kotlin differential coverage')
        return 0
    compiler_cp, stdlib = discover_toolchain()
    if not compiler_cp:
        print('no kotlin toolchain in gradle cache; skipping kotlin coverage')
        return 0

    patterns = sys.argv[1:] or [os.path.join(ROOT, 'examples', '*.epl')]
    files = sorted({path for pattern in patterns for path in glob.glob(pattern)})
    counts = {}
    for path in files:
        cat, detail = classify(path, compiler_cp, stdlib, java)
        counts[cat] = counts.get(cat, 0) + 1
        if cat != 'skip':
            print(f'  {cat:10} {os.path.basename(path):32} {detail}')
    print('\n=== counts ===')
    for k in ('pass', 'mismatch', 'runfail', 'buildfail', 'transpfail', 'skip'):
        if k in counts:
            print(f'  {k:10} {counts[k]}')
    measured = sum(v for k, v in counts.items() if k != 'skip')
    print(f'  measured   {measured}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
