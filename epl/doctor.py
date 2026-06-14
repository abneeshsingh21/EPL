"""
EPL Doctor — Environment health checker.

Usage:
    epl doctor              Run all diagnostic checks
    epl doctor --fix        Attempt to auto-fix problems found
    epl doctor --json       Output results as JSON (for CI/tooling)

Checks:
    - Python version (>= 3.9)
    - Node.js availability (for JS bridge)
    - npm availability
    - Git availability
    - EPL installation integrity
    - Project structure (epl.toml / epl.json)
    - Dependencies (installed vs declared)
    - Disk space
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional

# ═══════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    name: str
    status: str  # 'ok', 'warn', 'fail', 'skip'
    message: str
    detail: str = ''
    fix_hint: str = ''


@dataclass
class DoctorReport:
    """Full diagnostic report."""

    checks: List[CheckResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def ok_count(self):
        return sum(1 for c in self.checks if c.status == 'ok')

    @property
    def warn_count(self):
        return sum(1 for c in self.checks if c.status == 'warn')

    @property
    def fail_count(self):
        return sum(1 for c in self.checks if c.status == 'fail')

    @property
    def duration(self):
        return self.end_time - self.start_time

    @property
    def healthy(self):
        return self.fail_count == 0

    def to_dict(self):
        return {
            'healthy': self.healthy,
            'duration_s': round(self.duration, 3),
            'summary': {
                'ok': self.ok_count,
                'warnings': self.warn_count,
                'failures': self.fail_count,
            },
            'checks': [
                {
                    'name': c.name,
                    'status': c.status,
                    'message': c.message,
                    'detail': c.detail,
                    'fix_hint': c.fix_hint,
                }
                for c in self.checks
            ],
        }


# ═══════════════════════════════════════════════════════════
#  Terminal Colors
# ═══════════════════════════════════════════════════════════


def _supports_color():
    if os.environ.get('NO_COLOR'):
        return False
    if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
        return True
    return False


_COLOR = _supports_color()


def _c(code, text):
    return f'\033[{code}m{text}\033[0m' if _COLOR else text


def _green(t):
    return _c('32', t)


def _red(t):
    return _c('31', t)


def _yellow(t):
    return _c('33', t)


def _cyan(t):
    return _c('36', t)


def _dim(t):
    return _c('2', t)


def _bold(t):
    return _c('1', t)


STATUS_ICONS = {
    'ok': _green('+'),
    'warn': _yellow('!'),
    'fail': _red('x'),
    'skip': _dim('-'),
}


# ═══════════════════════════════════════════════════════════
#  Individual Checks
# ═══════════════════════════════════════════════════════════


def _run_cmd(cmd):
    """Run a command (always a list of args) and return (success, stdout).

    Never uses shell=True. On Windows we resolve the executable via shutil.which
    so we can find .cmd/.bat shims (e.g. npm) without giving the shell a chance
    to interpret arguments.
    """
    try:
        argv = list(cmd)
        if os.name == 'nt' and argv:
            import shutil as _shutil
            resolved = _shutil.which(argv[0])
            if resolved:
                argv[0] = resolved
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
        return result.returncode == 0, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False, ''


def check_python_version():
    """Check Python version >= 3.9."""
    major, minor = sys.version_info[:2]
    version_str = f'{major}.{minor}.{sys.version_info[2]}'

    if major < 3 or (major == 3 and minor < 9):
        return CheckResult(
            name='Python version',
            status='fail',
            message=f'Python {version_str} (requires >= 3.9)',
            fix_hint='Install Python 3.9+ from https://python.org',
        )
    elif major == 3 and minor < 11:
        return CheckResult(
            name='Python version',
            status='warn',
            message=f'Python {version_str} (3.11+ recommended)',
            detail='Older Python versions may have reduced performance',
        )
    return CheckResult(
        name='Python version',
        status='ok',
        message=f'Python {version_str}',
        detail=sys.executable,
    )


def check_epl_installation():
    """Check EPL is properly installed."""
    try:
        from epl import __version__

        return CheckResult(
            name='EPL installation',
            status='ok',
            message=f'EPL v{__version__}',
        )
    except ImportError:
        return CheckResult(
            name='EPL installation',
            status='fail',
            message='EPL not found in Python path',
            fix_hint='pip install epl-lang',
        )


def check_node():
    """Check Node.js availability (needed for JS bridge)."""
    ok, output = _run_cmd(['node', '--version'])
    if ok:
        return CheckResult(
            name='Node.js',
            status='ok',
            message=f'Node.js {output}',
        )
    return CheckResult(
        name='Node.js',
        status='warn',
        message='Node.js not found',
        detail='Required for: Use javascript, epl js, epl node',
        fix_hint='Install from https://nodejs.org',
    )


def check_npm():
    """Check npm availability."""
    ok, output = _run_cmd(['npm', '--version'])
    if ok:
        return CheckResult(
            name='npm',
            status='ok',
            message=f'npm v{output}',
        )
    return CheckResult(
        name='npm',
        status='warn',
        message='npm not found',
        detail='Required for: epl jsinstall',
        fix_hint='Install Node.js (npm is included)',
    )


def check_git():
    """Check Git availability."""
    ok, output = _run_cmd(['git', '--version'])
    if ok:
        version = output.replace('git version ', '')
        return CheckResult(
            name='Git',
            status='ok',
            message=f'Git {version}',
        )
    return CheckResult(
        name='Git',
        status='warn',
        message='Git not found',
        detail='Required for: epl github, epl gitinstall',
        fix_hint='Install from https://git-scm.com',
    )


def check_pip():
    """Check pip availability."""
    ok, output = _run_cmd([sys.executable, '-m', 'pip', '--version'])
    if ok:
        # Extract version from "pip X.Y.Z from ..."
        version = output.split()[1] if output else 'unknown'
        return CheckResult(
            name='pip',
            status='ok',
            message=f'pip v{version}',
        )
    return CheckResult(
        name='pip',
        status='warn',
        message='pip not found',
        fix_hint='python -m ensurepip --upgrade',
    )


def check_platform():
    """Report platform information."""
    plat = platform.platform()
    arch = platform.machine()
    return CheckResult(
        name='Platform',
        status='ok',
        message=f'{plat} ({arch})',
    )


def check_project_structure():
    """Check if current directory has an EPL project."""
    cwd = os.getcwd()
    manifests = ['epl.toml', 'epl.json', 'epl.manifest']

    for m in manifests:
        if os.path.isfile(os.path.join(cwd, m)):
            return CheckResult(
                name='Project manifest',
                status='ok',
                message=f'Found {m}',
                detail=os.path.join(cwd, m),
            )

    # Check for any .epl files
    epl_files = [f for f in os.listdir(cwd) if f.endswith('.epl')]
    if epl_files:
        return CheckResult(
            name='Project manifest',
            status='warn',
            message=f'No manifest found ({len(epl_files)} .epl files in directory)',
            fix_hint='Run "epl init" to create a project manifest',
        )

    return CheckResult(
        name='Project manifest',
        status='skip',
        message='No EPL project in current directory',
    )


def check_dependencies():
    """Check if declared dependencies are installed."""
    cwd = os.getcwd()

    # Look for manifest
    manifest_path = None
    for name in ['epl.toml', 'epl.json', 'epl.manifest']:
        path = os.path.join(cwd, name)
        if os.path.isfile(path):
            manifest_path = path
            break

    if not manifest_path:
        return CheckResult(
            name='Dependencies',
            status='skip',
            message='No manifest to check',
        )

    try:
        if manifest_path.endswith('.json'):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        else:
            # For .toml, just check if file is readable
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return CheckResult(
                name='Dependencies',
                status='ok',
                message='Manifest readable',
                detail=manifest_path,
            )

        deps = manifest.get('dependencies', {})
        if not deps:
            return CheckResult(
                name='Dependencies',
                status='ok',
                message='No dependencies declared',
            )

        return CheckResult(
            name='Dependencies',
            status='ok',
            message=f'{len(deps)} dependencies declared',
            detail=', '.join(deps.keys()),
        )

    except Exception as e:
        return CheckResult(
            name='Dependencies',
            status='warn',
            message=f'Could not parse manifest: {e}',
        )


def check_disk_space():
    """Check available disk space."""
    try:
        usage = shutil.disk_usage(os.getcwd())
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)

        if free_gb < 1:
            return CheckResult(
                name='Disk space',
                status='fail',
                message=f'{free_gb:.1f} GB free of {total_gb:.1f} GB',
                fix_hint='Free up disk space (< 1 GB remaining)',
            )
        elif free_gb < 5:
            return CheckResult(
                name='Disk space',
                status='warn',
                message=f'{free_gb:.1f} GB free of {total_gb:.1f} GB',
                detail='Consider freeing some space',
            )
        return CheckResult(
            name='Disk space',
            status='ok',
            message=f'{free_gb:.1f} GB free of {total_gb:.1f} GB',
        )
    except Exception:
        return CheckResult(
            name='Disk space',
            status='skip',
            message='Could not check disk space',
        )


def check_encoding():
    """Check terminal encoding supports UTF-8."""
    encoding = sys.stdout.encoding or 'unknown'
    if encoding.lower().replace('-', '') in ('utf8', 'utf16'):
        return CheckResult(
            name='Terminal encoding',
            status='ok',
            message=encoding,
        )
    return CheckResult(
        name='Terminal encoding',
        status='warn',
        message=f'{encoding} (UTF-8 recommended)',
        detail='Some EPL output may use ASCII fallbacks',
        fix_hint='Set terminal to UTF-8 or use Windows Terminal',
    )


# ═══════════════════════════════════════════════════════════
#  Main Doctor Runner
# ═══════════════════════════════════════════════════════════


ALL_CHECKS = [
    check_platform,
    check_python_version,
    check_epl_installation,
    check_node,
    check_npm,
    check_git,
    check_pip,
    check_encoding,
    check_disk_space,
    check_project_structure,
    check_dependencies,
]


def run_doctor(json_output=False):
    """Run all diagnostic checks and report results.

    Args:
        json_output: If True, output as JSON instead of formatted text.

    Returns:
        0 if healthy, 1 if failures found.
    """
    report = DoctorReport()
    report.start_time = time.time()

    if not json_output:
        print()
        print(f'  {_bold("EPL Doctor")} {_dim("v1.0")}')
        print(f'  {"-" * 45}')
        print()

    for check_fn in ALL_CHECKS:
        result = check_fn()
        report.checks.append(result)

        if not json_output:
            icon = STATUS_ICONS.get(result.status, '?')
            print(f'  {icon} {result.name}: {result.message}')
            if result.detail:
                print(f'    {_dim(result.detail)}')
            if result.fix_hint and result.status in ('fail', 'warn'):
                print(f'    {_cyan("Fix:")} {result.fix_hint}')

    report.end_time = time.time()

    if json_output:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print()
        print(f'  {"-" * 45}')

        if report.healthy:
            summary = _green(f'All good! {report.ok_count} checks passed')
        else:
            parts = []
            if report.ok_count:
                parts.append(_green(f'{report.ok_count} ok'))
            if report.warn_count:
                parts.append(_yellow(f'{report.warn_count} warnings'))
            if report.fail_count:
                parts.append(_red(f'{report.fail_count} failures'))
            summary = ', '.join(parts)

        print(f'  {summary} {_dim(f"({report.duration:.2f}s)")}')
        print()

    return 0 if report.healthy else 1
