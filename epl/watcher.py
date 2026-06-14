"""
EPL Watch Mode — File watcher with auto-reload.

Usage:
    epl watch <file.epl>              Watch and re-run on changes
    epl watch <file.epl> --test       Watch and re-run tests on changes
    epl watch <file.epl> --clear      Clear screen before each re-run
    epl watch <dir>                   Watch directory for changes
    epl watch <file.epl> --debounce=500   Set debounce in ms (default: 300)

Uses polling (no external dependencies) for maximum portability.
"""

import os
import subprocess
import sys
import time

# ═══════════════════════════════════════════════════════════
#  File Change Detection (polling-based, zero dependencies)
# ═══════════════════════════════════════════════════════════


class FileWatcher:
    """Watches files/directories for changes using os.stat polling."""

    def __init__(self, paths, extensions=None, debounce_ms=300):
        """
        Args:
            paths: List of file or directory paths to watch.
            extensions: Set of file extensions to watch (e.g., {'.epl'}).
            debounce_ms: Minimum ms between triggering events.
        """
        self.paths = [os.path.abspath(p) for p in paths]
        self.extensions = extensions or {'.epl'}
        self.debounce_s = debounce_ms / 1000.0
        self._snapshot = {}
        self._take_snapshot()

    def _collect_files(self):
        """Collect all watchable files from the configured paths."""
        files = []
        for path in self.paths:
            if os.path.isfile(path):
                files.append(path)
            elif os.path.isdir(path):
                for root, dirs, filenames in os.walk(path):
                    # Skip hidden dirs and __pycache__
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
                    for fname in filenames:
                        ext = os.path.splitext(fname)[1].lower()
                        if ext in self.extensions:
                            files.append(os.path.join(root, fname))
        return files

    def _take_snapshot(self):
        """Record mtime of all watched files."""
        self._snapshot = {}
        for filepath in self._collect_files():
            try:
                self._snapshot[filepath] = os.stat(filepath).st_mtime
            except (OSError, FileNotFoundError):
                pass

    def check_changes(self):
        """Check for file changes since last snapshot.

        Returns:
            List of (filepath, change_type) tuples.
            change_type is 'modified', 'added', or 'deleted'.
        """
        changes = []
        current = {}

        for filepath in self._collect_files():
            try:
                current[filepath] = os.stat(filepath).st_mtime
            except (OSError, FileNotFoundError):
                pass

        # Check for modifications and additions
        for filepath, mtime in current.items():
            if filepath not in self._snapshot:
                changes.append((filepath, 'added'))
            elif mtime != self._snapshot[filepath]:
                changes.append((filepath, 'modified'))

        # Check for deletions
        for filepath in self._snapshot:
            if filepath not in current:
                changes.append((filepath, 'deleted'))

        if changes:
            self._snapshot = current

        return changes

    def watch(self, callback, poll_interval=0.5):
        """Start watching for changes. Calls callback(changes) on detection.

        Args:
            callback: Function that receives list of (filepath, change_type).
            poll_interval: Seconds between polls (default: 0.5).
        """
        last_trigger = 0

        while True:
            time.sleep(poll_interval)
            changes = self.check_changes()
            if changes:
                now = time.time()
                if now - last_trigger < self.debounce_s:
                    continue
                last_trigger = now
                callback(changes)


# ═══════════════════════════════════════════════════════════
#  Watch Mode Runner
# ═══════════════════════════════════════════════════════════


def _color(code, text):
    """Apply ANSI color if stdout is a terminal."""
    if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
        return f'\033[{code}m{text}\033[0m'
    return text


def _green(t):
    return _color('32', t)


def _red(t):
    return _color('31', t)


def _cyan(t):
    return _color('36', t)


def _dim(t):
    return _color('2', t)


def _bold(t):
    return _color('1', t)


def _clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def _format_time():
    """Return formatted current time."""
    return time.strftime('%H:%M:%S')


def run_watch(target, flags=None, test_mode=False, clear=False, debounce_ms=300, timeout=None):
    """Run the watch loop for a file or directory.

    Args:
        target: File path or directory to watch.
        flags: Set of CLI flags to pass to the runner.
        test_mode: If True, run 'epl test' instead of 'epl run'.
        clear: If True, clear screen before each re-run.
        debounce_ms: Debounce interval in milliseconds.
        timeout: Per-run subprocess timeout in seconds, or None for no cap
            (default: None — the previous hardcoded 60s killed long-running
            programs that are common in watch workflows).
    """
    flags = flags or set()
    target = os.path.abspath(target)

    if not os.path.exists(target):
        print(f'{_red("Error:")} Path not found: {target}')
        return 1

    # Determine what to watch
    if os.path.isfile(target):
        watch_paths = [target]
        # Also watch the directory for new imports
        watch_dir = os.path.dirname(target)
        if watch_dir and watch_dir not in watch_paths:
            watch_paths.append(watch_dir)
    else:
        watch_paths = [target]

    display_target = os.path.relpath(target)
    mode_label = 'test' if test_mode else 'run'

    # Print banner
    print()
    print(f'  {_bold("EPL Watch Mode")} {_dim("v1.0")}')
    print(f'  {_cyan("Watching:")} {_bold(display_target)}')
    print(f'  {_cyan("Mode:")}    epl {mode_label}')
    print(f'  {_cyan("Debounce:")} {debounce_ms}ms')
    print(f'  {_dim("Press Ctrl+C to stop")}')
    print(f'  {"-" * 50}')

    # Initial run
    _execute(target, flags, test_mode, clear, timeout)

    # Create watcher
    watcher = FileWatcher(watch_paths, extensions={'.epl'}, debounce_ms=debounce_ms)

    def on_change(changes):
        changed_files = []
        for filepath, change_type in changes:
            rel = os.path.relpath(filepath)
            changed_files.append(f'{rel} ({change_type})')

        if clear:
            _clear_screen()

        print()
        print(f'  {_dim(_format_time())} {_cyan("Change detected:")}')
        for cf in changed_files[:5]:
            print(f'    {_dim(">")} {cf}')
        if len(changed_files) > 5:
            print(f'    {_dim(f"... and {len(changed_files) - 5} more")}')
        print(f'  {"-" * 50}')

        _execute(target, flags, test_mode, False, timeout)

    try:
        watcher.watch(on_change)
    except KeyboardInterrupt:
        print(f'\n  {_dim("Watch mode stopped.")}')
        return 0


def _execute(target, flags, test_mode, clear, timeout=None):
    """Execute the EPL file or test suite.

    timeout=None means "no per-run timeout"; pass a number to cap a single run.
    """
    if clear:
        _clear_screen()

    timestamp = _format_time()
    rel_target = os.path.relpath(target)

    if test_mode:
        print(f'\n  {_dim(timestamp)} {_cyan("Running tests:")} {rel_target}')
        cmd = [sys.executable, '-m', 'epl', 'test', target]
    else:
        print(f'\n  {_dim(timestamp)} {_cyan("Running:")} {rel_target}')
        cmd = [sys.executable, '-m', 'epl', 'run', target]

    # Pass through relevant flags
    for f in flags:
        if f not in ('--clear', '--test') and not f.startswith('--debounce') and not f.startswith('--timeout'):
            cmd.append(f)

    start = time.time()

    try:
        result = subprocess.run(
            cmd,
            cwd=os.getcwd(),
            timeout=timeout,
        )
        duration = time.time() - start
        exit_code = result.returncode

        if exit_code == 0:
            print(f'\n  {_green("OK")} {_dim(f"({duration:.2f}s)")}')
        else:
            print(f'\n  {_red(f"Exit code: {exit_code}")} {_dim(f"({duration:.2f}s)")}')

    except subprocess.TimeoutExpired:
        print(f'\n  {_red("TIMEOUT")} {_dim(f"Process killed after {timeout}s")}')
    except OSError as e:
        print(f'\n  {_red("ERROR")} {e}')

    print(f'  {_dim("Waiting for changes...")}')
