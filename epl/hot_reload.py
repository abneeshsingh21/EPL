"""EPL Hot Reload (v4.1)

File watcher that auto-restarts the server when source files change.
Works on Windows, Linux, and macOS without external dependencies.

Usage:
    from epl.hot_reload import HotReloader

    reloader = HotReloader(watch_dirs=['epl', 'templates', '.'],
                           patterns=['*.py', '*.epl', '*.html'],
                           callback=restart_fn)
    reloader.start()
"""
import os
import sys
import time
import threading
import logging
import fnmatch
import subprocess
import signal

_logger = logging.getLogger('epl.reload')


class FileWatcher:
    """Cross-platform file change detector using polling.

    Checks file mtimes every `interval` seconds. No external deps.
    """

    def __init__(self, watch_dirs=None, patterns=None, interval=1.0):
        self._dirs = watch_dirs or ['.']
        self._patterns = patterns or ['*.py', '*.epl', '*.html']
        self._interval = interval
        self._snapshots = {}  # path → mtime
        self._running = False
        self._thread = None
        self._callbacks = []

    def on_change(self, callback):
        """Register a callback: fn(changed_files: list[str])."""
        self._callbacks.append(callback)
        return callback

    def _matches(self, filename):
        return any(fnmatch.fnmatch(filename, p) for p in self._patterns)

    def _scan(self):
        """Scan all watched dirs, return dict of path → mtime."""
        snapshot = {}
        for d in self._dirs:
            if not os.path.isdir(d):
                continue
            for root, dirs, files in os.walk(d):
                # Skip hidden dirs and common excludes
                dirs[:] = [x for x in dirs if not x.startswith('.')
                           and x not in ('__pycache__', 'node_modules', '.git',
                                        'venv', 'env', '.venv')]
                for f in files:
                    if self._matches(f):
                        path = os.path.join(root, f)
                        try:
                            snapshot[path] = os.path.getmtime(path)
                        except OSError:
                            pass
        return snapshot

    def _check(self):
        """Check for changes, fire callbacks."""
        new = self._scan()
        changed = []

        # Detect modified or new files
        for path, mtime in new.items():
            if path not in self._snapshots or self._snapshots[path] != mtime:
                changed.append(path)

        # Detect deleted files
        for path in self._snapshots:
            if path not in new:
                changed.append(path)

        self._snapshots = new

        if changed:
            for cb in self._callbacks:
                try:
                    cb(changed)
                except Exception as e:
                    _logger.error(f'Watcher callback error: {e}')

    def _loop(self):
        """Background polling loop."""
        self._snapshots = self._scan()  # Initial snapshot
        while self._running:
            time.sleep(self._interval)
            if self._running:
                self._check()

    def start(self):
        """Start watching in background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name='epl-file-watcher')
        self._thread.start()
        _logger.info(f'File watcher started: dirs={self._dirs}, patterns={self._patterns}')

    def stop(self):
        """Stop watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        _logger.info('File watcher stopped')


class HotReloader:
    """Auto-restart server when source files change.

    Strategy: re-execute the current process with the same arguments.
    This is the same approach used by Flask and Django's dev servers.
    """

    def __init__(self, watch_dirs=None, patterns=None, interval=1.0):
        self._watcher = FileWatcher(
            watch_dirs=watch_dirs or ['.'],
            patterns=patterns or ['*.py', '*.epl', '*.html'],
            interval=interval
        )
        self._watcher.on_change(self._on_change)
        self._restart_pending = False
        self._child = None
        self._is_child = os.environ.get('EPL_RELOAD_CHILD') == '1'

    def _on_change(self, changed_files):
        """Handle file changes — trigger restart."""
        short = [os.path.basename(f) for f in changed_files[:5]]
        _logger.info(f'Files changed: {", ".join(short)} — restarting...')
        print(f'\n  [HOT RELOAD] Files changed: {", ".join(short)}')
        print(f'  [HOT RELOAD] Restarting server...\n')
        self._restart_pending = True

    def run_with_reload(self, target_fn, *args, **kwargs):
        """Run target_fn with hot-reload support.

        If this is the parent process, it spawns a child and watches for changes.
        If this is the child process, it runs target_fn directly.
        """
        if self._is_child:
            # We're the child — just run the server
            target_fn(*args, **kwargs)
            return

        # We're the parent — spawn child and watch
        self._watcher.start()
        while True:
            env = os.environ.copy()
            env['EPL_RELOAD_CHILD'] = '1'
            cmd = [sys.executable] + sys.argv
            _logger.info(f'Starting child process: {" ".join(cmd)}')
            print('  [HOT RELOAD] Server starting (watching for changes)...')

            try:
                self._child = subprocess.Popen(cmd, env=env)
                while not self._restart_pending:
                    ret = self._child.poll()
                    if ret is not None:
                        # Child exited on its own
                        if ret != 0:
                            _logger.warning(f'Child exited with code {ret}, waiting for fix...')
                            print(f'  [HOT RELOAD] Server crashed (exit {ret}). Waiting for file change...')
                            # Wait for a file change before restarting
                            self._restart_pending = False
                            while not self._restart_pending:
                                time.sleep(0.5)
                        break
                    time.sleep(0.2)

                # Kill child if still running
                if self._child.poll() is None:
                    self._child.terminate()
                    self._child.wait(timeout=5)
            except KeyboardInterrupt:
                if self._child and self._child.poll() is None:
                    self._child.terminate()
                    self._child.wait(timeout=5)
                break
            finally:
                self._restart_pending = False

        self._watcher.stop()

    def start_watching(self):
        """Start file watching only (no process management).

        Use when you want manual control over the restart logic.
        Returns the FileWatcher for custom callback registration.
        """
        self._watcher.start()
        return self._watcher

    def stop(self):
        """Stop the reloader."""
        self._watcher.stop()
        if self._child and self._child.poll() is None:
            self._child.terminate()
