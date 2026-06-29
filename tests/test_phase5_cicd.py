"""
EPL v9.4.0 Phase 5 Test Suite — CI/CD hardening + dependency fixes.

Verifies statically (no network, no CI runner) that:
  1. pyproject.toml declares flask and requests as required runtime deps.
  2. All optional deps carry upper-bound version caps (no open-ended >=X.Y).
  3. mypy is declared in [dev] optional deps.
  4. ci.yml test matrix includes Python 3.9 and 3.10.
  5. ci.yml contains a mypy / typecheck job.
  6. ci.yml runs the full `pytest tests/` suite (so security/reliability test
     files are included by construction, not via a brittle per-file whitelist).
  7. pyproject.toml requires-python is consistent with the CI matrix.
"""

import os
import re
import sys
from functools import wraps

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PYPROJECT = os.path.join(REPO_ROOT, 'pyproject.toml')
CI_YML = os.path.join(REPO_ROOT, '.github', 'workflows', 'ci.yml')


# ── Minimal test harness ─────────────────────────────────────────────────────


class _TrackerState:
    current = None
    total_pass = 0
    total_fail = 0


def _start_tracker():
    _TrackerState.current = {'passed': 0, 'failed': 0, 'failures': []}


def _finish_tracker():
    t = _TrackerState.current
    _TrackerState.current = None
    if t is None:
        return
    _TrackerState.total_pass += t['passed']
    _TrackerState.total_fail += t['failed']
    if t['failures']:
        raise AssertionError('\n'.join(t['failures']))


def _tracked_test(fn):
    @wraps(fn)
    def wrapper():
        _start_tracker()
        try:
            fn()
        finally:
            _finish_tracker()

    return wrapper


def check(name, condition, detail=''):
    t = _TrackerState.current
    if t is None:
        raise RuntimeError('check() called outside an active test tracker.')
    if condition:
        print(f'  PASS: {name}')
        t['passed'] += 1
    else:
        print(f'  FAIL: {name} {detail}')
        t['failed'] += 1
        t['failures'].append(f'{name}: {detail}' if detail else name)


# ══════════════════════════════════════════════════════════════════════════════
# P5-1  pyproject.toml — required runtime deps
# ══════════════════════════════════════════════════════════════════════════════


@_tracked_test
def test_pyproject_runtime_deps():
    print('\n=== P5-1: pyproject.toml — required runtime dependencies ===')

    src = open(PYPROJECT, encoding='utf-8').read()

    # T1: [project.dependencies] section exists
    check(
        '[project.dependencies] section present',
        'dependencies = [' in src
        or 'dependencies=\n' in src
        or re.search(r'^\s*dependencies\s*=\s*\[', src, re.MULTILINE) is not None,
    )

    # T2: flask listed as required runtime dep
    check(
        'flask in [project.dependencies]',
        bool(re.search(r'dependencies\s*=\s*\[([^\]]*flask[^\]]*)\]', src, re.DOTALL)),
    )

    # T3: requests listed as required runtime dep
    check(
        'requests in [project.dependencies]',
        bool(re.search(r'dependencies\s*=\s*\[([^\]]*requests[^\]]*)\]', src, re.DOTALL)),
    )

    # T4: flask has a lower-bound version
    check('flask has lower-bound (>=3.0)', bool(re.search(r'flask>=\d', src)))

    # T5: flask has an upper-bound version (no open-ended dep)
    check('flask has upper-bound (<4.0)', bool(re.search(r'flask>=[\d.,]+,<[\d.]+', src)))

    # T6: requests has a lower-bound
    check('requests has lower-bound (>=2.31)', bool(re.search(r'requests>=\d', src)))

    # T7: requests has an upper-bound
    check('requests has upper-bound (<3.0)', bool(re.search(r'requests>=[\d.,]+,<[\d.]+', src)))

    # T8: requires-python is >=3.9
    check('requires-python is >=3.9', 'requires-python = ">=3.9"' in src)

    # T9: pyproject parses as valid TOML (stdlib tomllib / tomli fallback)
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            tomllib = None  # type: ignore[assignment]

    if tomllib is not None:
        try:
            with open(PYPROJECT, 'rb') as f:
                data = tomllib.load(f)
            check('pyproject.toml parses as valid TOML', True)
            deps = data.get('project', {}).get('dependencies', [])
            check('flask in parsed dependencies', any('flask' in d for d in deps))
            check('requests in parsed dependencies', any('requests' in d for d in deps))
        except Exception as e:
            check('pyproject.toml parses as valid TOML', False, str(e))
    else:
        # Fall back to regex-only if no TOML parser available
        print('  SKIP: no tomllib/tomli — skipping parsed TOML checks')


# ══════════════════════════════════════════════════════════════════════════════
# P5-2  pyproject.toml — optional dep upper bounds
# ══════════════════════════════════════════════════════════════════════════════


@_tracked_test
def test_pyproject_optional_upper_bounds():
    print('\n=== P5-2: pyproject.toml — optional dep upper bounds ===')

    src = open(PYPROJECT, encoding='utf-8').read()

    # Extract the [project.optional-dependencies] block
    m = re.search(
        r'\[project\.optional-dependencies\](.*?)(?=^\[|\Z)', src, re.DOTALL | re.MULTILINE
    )
    check('[project.optional-dependencies] block found', m is not None)
    if m is None:
        return

    opt_block = m.group(1)

    # Pull out all quoted dep specs like "flask>=3.0,<4.0"
    dep_specs = re.findall(r'"([^"]+)"', opt_block)

    # Each spec that has >= must also have <
    # Exceptions: platform markers (;), extras ([...]) — still need upper bound
    no_upper = []
    for spec in dep_specs:
        # Strip marker
        spec_no_marker = spec.split(';')[0].strip()
        # Only check specs with a lower bound (>=)
        if '>=' in spec_no_marker and '<' not in spec_no_marker:
            no_upper.append(spec)

    check(
        'All optional deps have upper-bound caps',
        len(no_upper) == 0,
        f'Missing upper bound: {no_upper}',
    )

    # T2: mypy is in dev optional deps
    check(
        'mypy in [dev] optional deps',
        bool(re.search(r'dev\s*=\s*\[([^\]]*mypy[^\]]*)\]', src, re.DOTALL)),
    )

    # T3: mypy has a lower-bound
    check('mypy has lower-bound (>=1.8)', bool(re.search(r'mypy>=\d', src)))

    # T4: mypy has an upper-bound
    check('mypy has upper-bound (<2.0)', bool(re.search(r'mypy>=[\d.,]+,<[\d.]+', src)))

    # T5: Spot-check a few key optional packages have upper bounds
    for pkg in ('waitress', 'uvicorn', 'boto3', 'keyring', 'prompt_toolkit', 'pygments'):
        has_upper = bool(re.search(rf'{pkg}>=[\d.,]+,<[\d.]+', src))
        check(f'{pkg} has upper bound', has_upper)


# ══════════════════════════════════════════════════════════════════════════════
# P5-3  ci.yml — Python version matrix
# ══════════════════════════════════════════════════════════════════════════════


@_tracked_test
def test_ci_python_matrix():
    print('\n=== P5-3: ci.yml — Python version matrix ===')

    src = open(CI_YML, encoding='utf-8').read()

    # T1: 3.9 in matrix
    check("Python '3.9' in ci.yml matrix", "'3.9'" in src)

    # T2: 3.10 in matrix
    check("Python '3.10' in ci.yml matrix", "'3.10'" in src)

    # T3: 3.11 still present
    check("Python '3.11' in ci.yml matrix", "'3.11'" in src)

    # T4: 3.12 still present
    check("Python '3.12' in ci.yml matrix", "'3.12'" in src)

    # T5: Matrix declares python-version as a list (not single value)
    matrix_line = re.search(r'python-version:\s*\[([^\]]+)\]', src)
    check('python-version is a list in matrix', matrix_line is not None)
    if matrix_line:
        versions_in_matrix = matrix_line.group(1)
        check(
            'Matrix has at least 4 Python versions', versions_in_matrix.count("'") >= 8
        )  # 4 versions × 2 quotes each

    # T6: requires-python in pyproject matches the CI minimum
    pyproject_src = open(PYPROJECT, encoding='utf-8').read()
    requires = re.search(r'requires-python\s*=\s*"([^"]+)"', pyproject_src)
    if requires:
        req_str = requires.group(1)
        check('pyproject requires-python >= 3.9', '3.9' in req_str or '3.8' in req_str)
        # The CI matrix minimum (3.9) should be consistent with pyproject
        ci_has_39 = "'3.9'" in src
        pyproject_allows_39 = '3.9' in req_str or not req_str.startswith('>=3.1')
        check('CI minimum matches pyproject requires-python', ci_has_39 and pyproject_allows_39)


# ══════════════════════════════════════════════════════════════════════════════
# P5-4  ci.yml — mypy / typecheck job
# ══════════════════════════════════════════════════════════════════════════════


@_tracked_test
def test_ci_mypy_job():
    print('\n=== P5-4: ci.yml — mypy typecheck job ===')

    src = open(CI_YML, encoding='utf-8').read()

    # T1: A typecheck or mypy job exists
    has_typecheck_job = bool(re.search(r'^\s*typecheck\s*:', src, re.MULTILINE))
    has_mypy_job = bool(re.search(r'^\s*mypy\s*:', src, re.MULTILINE))
    check('typecheck or mypy job exists in ci.yml', has_typecheck_job or has_mypy_job)

    # T2: mypy command is invoked
    check('mypy command invoked in ci.yml', 'mypy' in src)

    # T3: mypy targets the epl/ directory
    check('mypy targets epl/', bool(re.search(r'mypy\s+epl/', src)))

    # T4: Job runs on a defined Python version
    # Find the typecheck job block — it starts after "  typecheck:" and ends
    # before the next top-level job key (a line with exactly 2-space indent + word + colon)
    typecheck_idx = src.find('\n  typecheck:')
    if typecheck_idx >= 0:
        # Find the next top-level job after typecheck
        next_job = re.search(r'\n  \w[\w-]*:\n', src[typecheck_idx + 1 :])
        end_idx = (typecheck_idx + 1 + next_job.start()) if next_job else len(src)
        block = src[typecheck_idx:end_idx]
        check('typecheck job specifies python-version', 'python-version' in block)
    else:
        check('typecheck job specifies python-version', False, 'typecheck block not found')

    # T5: mypy is installed in the typecheck job
    check(
        'mypy installed in CI (via pip install or dev extra)',
        'mypy' in src and ('.[dev]' in src or 'pip install mypy' in src),
    )

    # T6: The job is not skipped (no `if: false`)
    check(
        'typecheck job is not unconditionally skipped',
        not bool(re.search(r'typecheck.*?if:\s*false', src, re.DOTALL)),
    )


# ══════════════════════════════════════════════════════════════════════════════
# P5-5  ci.yml — security / reliability tests included in whitelist
# ══════════════════════════════════════════════════════════════════════════════


@_tracked_test
def test_ci_security_tests_included():
    print('\n=== P5-5: ci.yml — full suite runs (security tests included by construction) ===')

    src = open(CI_YML, encoding='utf-8').read()

    # Phase 3 consolidation replaced the hardcoded per-file whitelist (which
    # silently dropped any newly-added test file, including security ones) with
    # a single full-suite run. The original intent of this test — "security and
    # reliability tests must execute in CI" — is now satisfied *by construction*:
    # `pytest tests/` collects every test_*.py, so no file can be omitted.
    #
    # Assert the stronger guarantee instead of the brittle whitelist: CI runs the
    # whole tests/ directory and does NOT re-introduce a curated file list.
    runs_full_suite = bool(re.search(r'pytest\s+tests/(?:\s|$)', src, re.MULTILINE))
    check('ci.yml runs the full `pytest tests/` suite', runs_full_suite)

    # The previously-omitted security/reliability suites are real files that the
    # full run therefore covers. Confirm they still exist on disk (a rename would
    # otherwise silently shrink coverage without any whitelist to flag it).
    tests_dir = os.path.join(REPO_ROOT, 'tests')
    for tf in (
        'test_phase3_reliability.py',
        'test_phase4_security.py',
        'test_security_hardening.py',
    ):
        check(
            f'{tf} exists and is collected by `pytest tests/`',
            os.path.isfile(os.path.join(tests_dir, tf)),
        )

    # Guard against regression: the brittle hardcoded whitelist must not return.
    check('no per-file test whitelist re-introduced', 'Run stable test suite' not in src)


# ══════════════════════════════════════════════════════════════════════════════
# P5-6  Smoke — pyproject.toml is machine-readable (setuptools dry-run)
# ══════════════════════════════════════════════════════════════════════════════


@_tracked_test
def test_pyproject_machine_readable():
    print('\n=== P5-6: pyproject.toml — machine-readable sanity check ===')

    src = open(PYPROJECT, encoding='utf-8').read()

    # T1: build-system section present
    check('[build-system] present', '[build-system]' in src)

    # T2: project name is set
    check('project name declared', bool(re.search(r'name\s*=\s*"eplang"', src)))

    # T3: dynamic version
    check('dynamic version declared', 'dynamic = ["version"]' in src)

    # T4: [tool.pytest.ini_options] still present
    check('[tool.pytest.ini_options] present', '[tool.pytest.ini_options]' in src)

    # T5: [tool.mypy] section still present
    check('[tool.mypy] section present', '[tool.mypy]' in src)

    # T6: [tool.ruff] still present
    check('[tool.ruff] present', '[tool.ruff]' in src)

    # T7: No syntax errors (balanced brackets in dependencies block)
    deps_block = re.search(r'dependencies\s*=\s*\[(.*?)\]', src, re.DOTALL)
    if deps_block:
        inner = deps_block.group(1)
        check('dependencies block balanced', inner.count('[') == inner.count(']'))

    # T8: All declared classifiers reference Python 3.9+
    check('Classifier 3.9 present', 'Programming Language :: Python :: 3.9' in src)
    check('Classifier 3.10 present', 'Programming Language :: Python :: 3.10' in src)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════


def main():
    print('=' * 60)
    print('  EPL v9.4.0 Phase 5 CI/CD Tests')
    print('=' * 60)

    test_functions = [
        test_pyproject_runtime_deps,
        test_pyproject_optional_upper_bounds,
        test_ci_python_matrix,
        test_ci_mypy_job,
        test_ci_security_tests_included,
        test_pyproject_machine_readable,
    ]

    for fn in test_functions:
        try:
            fn()
        except AssertionError:
            pass

    total = _TrackerState.total_pass + _TrackerState.total_fail
    print(f'\n{"=" * 60}')
    print(
        f'  Results: {_TrackerState.total_pass}/{total} passed, {_TrackerState.total_fail} failed'
    )
    print(f'{"=" * 60}')
    return _TrackerState.total_fail == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
