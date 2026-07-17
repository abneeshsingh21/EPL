"""Guardrail: the Android EPLRuntime shim must stay byte-identical.

The Android APK path is verified end-to-end (real assembleDebug). Any refactor
of the runtime (e.g. extracting a shared core for the console target) must not
change what Android emits. These goldens lock that: if the rendered runtime
drifts, this fails and the diff is the change to review.

If a change to the Android runtime is *intended*, regenerate the fixtures:
    python -c "from epl.kotlin_gen import AndroidProjectGenerator as A; \
        open('tests/fixtures/android_epl_runtime__com_epl_app.kt','w',\
        encoding='utf-8',newline='\\n').write(A('X','com.epl.app')._epl_runtime_kt())"
"""

import os

import pytest
from epl.kotlin_gen import AndroidProjectGenerator

FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.mark.parametrize(
    'pkg,fixture',
    [
        ('com.epl.app', 'android_epl_runtime__com_epl_app.kt'),
        ('com.acme.demo', 'android_epl_runtime__com_acme_demo.kt'),
    ],
)
def test_android_runtime_matches_golden(pkg, fixture):
    got = AndroidProjectGenerator('X', pkg)._epl_runtime_kt()
    with open(os.path.join(FIX, fixture), 'r', encoding='utf-8') as fh:
        want = fh.read()
    assert got == want, (
        f'Android EPLRuntime for package {pkg} drifted from golden fixture. '
        'If intended, regenerate the fixture (see module docstring).'
    )
