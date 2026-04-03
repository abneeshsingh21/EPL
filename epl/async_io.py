"""
EPL Async I/O Event Loop v4.0
Production-grade asynchronous I/O with:
  - Event loop (asyncio-backed)
  - Async/await coroutine support
  - Async timers, intervals
  - Async file I/O
  - Async HTTP client
  - Channel-based communication (Go-style)
  - Task groups for structured concurrency
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future


# ═══════════════════════════════════════════════════════════
#  Event Loop Singleton
# ═══════════════════════════════════════════════════════════

class EPLEventLoop:
    """Singleton event loop for EPL async operations."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._loop = None
        self._thread = None
        self._executor = ThreadPoolExecutor(max_workers=16)
        self._tasks = {}
        self._channels = {}
        self._initialized = True

    def _ensure_loop(self):
        """Start the event loop in a background thread if not running."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run_coroutine(self, coro):
        """Schedule a coroutine on the event loop and return a Future."""
        self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future

    def run_sync(self, func, *args):
        """Run a sync function in the thread pool."""
        return self._executor.submit(func, *args)

    def shutdown(self, timeout: float = 5.0):
        """Gracefully shut down the event loop.
        
        Drains pending tasks (up to timeout seconds), then stops the loop
        and shuts down the thread pool.
        """
        if self._loop and self._loop.is_running():
            # Cancel all pending tasks and give them time to finish
            async def _drain():
                tasks = [t for t in asyncio.all_tasks(self._loop)
                         if t is not asyncio.current_task()]
                for t in tasks:
                    t.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            try:
                future = asyncio.run_coroutine_threadsafe(_drain(), self._loop)
                future.result(timeout=timeout)
            except Exception:
                pass  # Best-effort drain
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._executor.shutdown(wait=True, cancel_futures=True)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)


# ═══════════════════════════════════════════════════════════
#  Async Task
# ═══════════════════════════════════════════════════════════

class EPLTask:
    """Represents an async task with status tracking."""

    def __init__(self, name: str, future):
        self.name = name
        self._future = future
        self.status = "running"
        self._callbacks = []

    @property
    def done(self):
        return self._future.done()

    @property
    def result(self):
        if self._future.done():
            self.status = "completed"
            return self._future.result()
        return None

    def wait(self, timeout=None):
        """Block until task completes."""
        try:
            result = self._future.result(timeout=timeout)
            self.status = "completed"
            return result
        except Exception as e:
            self.status = "failed"
            raise

    def cancel(self):
        self._future.cancel()
        self.status = "cancelled"

    def on_complete(self, callback):
        """Register a callback for when task completes."""
        self._callbacks.append(callback)
        self._future.add_done_callback(lambda f: callback(f.result() if not f.cancelled() else None))


# ═══════════════════════════════════════════════════════════
#  Channel — use canonical implementation from concurrency.py
# ═══════════════════════════════════════════════════════════

# REMOVED: Duplicate EPLChannel class (Gap 7 fix).
# The canonical implementation is in concurrency.py (thread-safe, queue-based).
# Import it here for backward compatibility.
from epl.concurrency import EPLChannel


# ═══════════════════════════════════════════════════════════
#  Task Group (structured concurrency)
# ═══════════════════════════════════════════════════════════

class EPLTaskGroup:
    """Run multiple tasks concurrently, wait for all to complete."""

    def __init__(self):
        self._tasks = []

    def add(self, name: str, func, *args):
        loop = EPLEventLoop()
        if asyncio.iscoroutinefunction(func):
            future = loop.run_coroutine(func(*args))
        else:
            future = loop.run_sync(func, *args)
        task = EPLTask(name, future)
        self._tasks.append(task)
        return task

    def wait_all(self, timeout=None):
        """Wait for all tasks to complete."""
        results = []
        deadline = time.time() + timeout if timeout else None
        for task in self._tasks:
            remaining = (deadline - time.time()) if deadline else None
            if remaining is not None and remaining <= 0:
                break
            results.append(task.wait(timeout=remaining))
        return results

    @property
    def all_done(self):
        return all(t.done for t in self._tasks)


# ═══════════════════════════════════════════════════════════
#  Async Utilities  (registered as stdlib functions)
# ═══════════════════════════════════════════════════════════

async def async_sleep(seconds):
    """Non-blocking sleep."""
    await asyncio.sleep(seconds)


async def async_read_file(path):
    """Async file read using thread pool."""
    loop = asyncio.get_event_loop()
    def _read():
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return await loop.run_in_executor(None, _read)


async def async_write_file(path, content):
    """Async file write using thread pool."""
    loop = asyncio.get_event_loop()
    def _write():
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    return await loop.run_in_executor(None, _write)


async def async_http_get(url):
    """Async HTTP GET using urllib (no external deps)."""
    import urllib.request
    loop = asyncio.get_event_loop()
    def _get():
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read().decode('utf-8')
    return await loop.run_in_executor(None, _get)


async def async_http_post(url, data):
    """Async HTTP POST."""
    import urllib.request
    import json as _json
    loop = asyncio.get_event_loop()
    def _post():
        payload = _json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode('utf-8')
    return await loop.run_in_executor(None, _post)


# ═══════════════════════════════════════════════════════════
#  Timer — use canonical implementation from concurrency.py
# ═══════════════════════════════════════════════════════════

# REMOVED: Duplicate EPLTimer class (Gap 7 fix).
# The canonical implementation is in concurrency.py (threading.Timer-based).
from epl.concurrency import EPLTimer


class EPLInterval:
    """Repeating timer that fires a callback at intervals (async-native)."""

    def __init__(self, interval_seconds, callback):
        self._interval = interval_seconds
        self._callback = callback
        self._running = True
        self._loop = EPLEventLoop()
        self._task = self._loop.run_coroutine(self._run())

    async def _run(self):
        while self._running:
            await asyncio.sleep(self._interval)
            if self._running:
                self._callback()

    def stop(self):
        self._running = False


# ═══════════════════════════════════════════════════════════
#  Stdlib Registration Helper
# ═══════════════════════════════════════════════════════════

def register_async_builtins():
    """Return dict of async-related builtin functions for the interpreter."""
    return {
        'async_sleep': lambda secs: EPLEventLoop().run_coroutine(async_sleep(secs)),
        'create_channel': lambda cap=0: EPLChannel(cap),
        'create_task_group': lambda: EPLTaskGroup(),
        'create_timer': lambda delay, cb: EPLTimer(delay, cb),
        'create_interval': lambda interval, cb: EPLInterval(interval, cb),
    }
