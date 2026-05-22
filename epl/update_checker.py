"""
EPL Update Checker — Non-blocking PyPI version check.

Checks for newer versions of EPL on PyPI at most once every 24 hours.
Results are cached locally to avoid unnecessary network requests.
Designed to never interfere with normal CLI operation.

Usage:
    from epl.update_checker import check_for_updates
    check_for_updates()  # Non-blocking, prints notification if update available
"""

import json
import os
import sys
import threading
import time


def _get_version():
    """Lazy version getter to avoid circular imports."""
    try:
        from epl import __version__
        return __version__
    except ImportError:
        return '0.0.0'

# ── Configuration ────────────────────────────────────────

_PYPI_URL = 'https://pypi.org/pypi/eplang/json'
_CHECK_INTERVAL = 86400  # 24 hours in seconds
_REQUEST_TIMEOUT = 3  # seconds — fail fast
_PACKAGE_NAME = 'eplang'


def _get_cache_dir():
    """Get the EPL cache directory (~/.epl/)."""
    home = os.path.expanduser('~')
    cache_dir = os.path.join(home, '.epl')
    return cache_dir


def _get_cache_path():
    """Get the path to the update check cache file."""
    return os.path.join(_get_cache_dir(), 'update_check.json')


def _read_cache():
    """Read the cached update check result."""
    path = _get_cache_path()
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError, KeyError):
        pass
    return None


def _write_cache(latest_version):
    """Write the update check result to cache."""
    cache_dir = _get_cache_dir()
    try:
        os.makedirs(cache_dir, exist_ok=True)
        path = _get_cache_path()
        data = {
            'last_check': time.time(),
            'latest_version': latest_version,
            'current_version': _get_version(),
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass  # Silently fail — cache is optional


def _parse_version(version_str):
    """Parse a version string into a comparable tuple.

    Handles standard semver: '7.6.0' → (7, 6, 0)
    Gracefully handles non-numeric segments.
    """
    parts = []
    for part in version_str.strip().split('.'):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _is_newer(latest, current):
    """Check if latest version is newer than current."""
    return _parse_version(latest) > _parse_version(current)


def _format_notification(latest_version):
    """Format the update notification message."""
    current = _get_version()
    is_tty = hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()
    no_color = os.environ.get('NO_COLOR')

    if is_tty and not no_color:
        # ANSI-colored notification
        yellow = '\033[33m'
        cyan = '\033[36m'
        bold = '\033[1m'
        reset = '\033[0m'
        dim = '\033[2m'
        return (
            f'\n{dim}╭─────────────────────────────────────────────╮{reset}\n'
            f'{dim}│{reset}  {yellow}⚡ EPL {bold}v{latest_version}{reset}{yellow} available{reset}'
            f'  {dim}(you have v{current}){reset}    {dim}│{reset}\n'
            f'{dim}│{reset}  {cyan}pip install --upgrade {_PACKAGE_NAME}{reset}'
            f'             {dim}│{reset}\n'
            f'{dim}╰─────────────────────────────────────────────╯{reset}\n'
        )
    else:
        # Plain text fallback
        return (
            f'\n  EPL v{latest_version} available (you have v{current}).\n'
            f'  Update: pip install --upgrade {_PACKAGE_NAME}\n'
        )


def _fetch_latest_version():
    """Fetch the latest version from PyPI. Returns version string or None."""
    try:
        from urllib.request import Request, urlopen

        req = Request(_PYPI_URL, headers={'Accept': 'application/json'})
        with urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('info', {}).get('version')
    except Exception:
        return None  # Network error, timeout, parse error — all silently ignored


def _check_and_notify():
    """Background worker: fetch latest version and print notification if newer."""
    latest = _fetch_latest_version()
    if latest is None:
        return

    # Cache the result regardless
    _write_cache(latest)

    # Notify only if a newer version exists
    if _is_newer(latest, _get_version()):
        msg = _format_notification(latest)
        # Print to stderr so it doesn't interfere with program stdout
        try:
            sys.stderr.write(msg)
            sys.stderr.flush()
        except OSError:
            pass


def _should_check():
    """Determine if we should perform a check based on cache."""
    cache = _read_cache()
    if cache is None:
        return True

    last_check = cache.get('last_check', 0)
    elapsed = time.time() - last_check

    # If cache is fresh, check if we should show a cached notification
    if elapsed < _CHECK_INTERVAL:
        cached_latest = cache.get('latest_version')
        if cached_latest and _is_newer(cached_latest, _get_version()):
            # Show cached notification (no network needed)
            msg = _format_notification(cached_latest)
            try:
                sys.stderr.write(msg)
                sys.stderr.flush()
            except OSError:
                pass
        return False

    return True


def check_for_updates():
    """Check for EPL updates in the background.

    This function is safe to call from any context:
    - Non-blocking (runs in a daemon thread)
    - Checks at most once per 24 hours
    - Fails silently on any error
    - Respects NO_COLOR and EPL_NO_UPDATE_CHECK environment variables
    - Prints to stderr to avoid interfering with program output
    """
    # Allow users to disable update checks
    if os.environ.get('EPL_NO_UPDATE_CHECK', '').lower() in ('1', 'true', 'yes'):
        return

    # Don't check in CI environments
    ci_vars = ('CI', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_URL', 'TRAVIS')
    if any(os.environ.get(var) for var in ci_vars):
        return

    # Don't check if not connected to a terminal
    if not (hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()):
        return

    if not _should_check():
        return

    # Run the actual check in a background daemon thread
    thread = threading.Thread(target=_check_and_notify, daemon=True)
    thread.start()
    # Don't join — let it finish in the background while the program runs
