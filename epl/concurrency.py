"""
EPL Concurrency Module (v2.0)
Production-grade concurrency primitives: Mutex, RWLock, Channel, Semaphore,
AtomicCounter, ThreadPool, and structured concurrency patterns.

All primitives are thread-safe and designed for EPL's English-syntax paradigm.
"""

import threading
import queue
import time
import concurrent.futures
from typing import Any, Optional, Callable, List
from collections import deque


class EPLMutex:
    """Mutual exclusion lock for thread-safe resource access.
    
    Usage in EPL:
        Create lock equal to Mutex().
        lock.acquire().
        ... critical section ...
        lock.release().
    Or:
        lock.with_lock(lambda -> do_something()).
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._owner = None

    def acquire(self, timeout: float = -1) -> bool:
        if timeout < 0:
            result = self._lock.acquire(blocking=True)
        else:
            result = self._lock.acquire(timeout=timeout)
        if result:
            self._owner = threading.current_thread().ident
        return result

    def release(self):
        self._owner = None
        self._lock.release()

    def is_locked(self) -> bool:
        if self._lock.acquire(blocking=False):
            self._lock.release()
            return False
        return True

    def with_lock(self, func: Callable) -> Any:
        """Execute func while holding the lock, then release."""
        self.acquire()
        try:
            return func()
        finally:
            self.release()

    def __repr__(self):
        status = "locked" if self.is_locked() else "unlocked"
        return f"<Mutex {status}>"


class EPLRWLock:
    """Read-Write lock allowing multiple readers or one writer.
    
    Multiple threads can read simultaneously, but writing is exclusive.
    Writers have priority: when a writer is waiting, new readers are blocked
    to prevent writer starvation.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._read_ready = threading.Condition(self._lock)
        self._readers = 0
        self._writers_waiting = 0  # Prevents writer starvation

    def acquire_read(self):
        with self._read_ready:
            # Block new readers if writers are waiting (prevents starvation)
            while self._writers_waiting > 0:
                self._read_ready.wait()
            self._readers += 1

    def release_read(self):
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self):
        self._lock.acquire()
        self._writers_waiting += 1
        while self._readers > 0:
            self._read_ready.wait()
        self._writers_waiting -= 1

    def release_write(self):
        self._read_ready.notify_all()
        self._lock.release()

    def __repr__(self):
        return f"<RWLock readers={self._readers} writers_waiting={self._writers_waiting}>"


class EPLChannel:
    """Go-style channel for thread-safe message passing.
    
    Usage in EPL:
        Create ch equal to Channel(10).  Note: buffered channel, capacity 10
        ch.send("hello").
        Create msg equal to ch.receive().
    """
    def __init__(self, capacity: int = 0):
        if capacity <= 0:
            self._queue = queue.Queue(maxsize=1)  # unbuffered: sync handoff
        else:
            self._queue = queue.Queue(maxsize=capacity)
        self._closed = False
        self._capacity = capacity

    def send(self, value: Any, timeout: float = None):
        if self._closed:
            raise RuntimeError("Cannot send on closed channel")
        try:
            self._queue.put(value, block=True, timeout=timeout)
        except queue.Full:
            raise RuntimeError("Channel send timed out")

    def receive(self, timeout: float = None) -> Any:
        try:
            return self._queue.get(block=True, timeout=timeout)
        except queue.Empty:
            if self._closed:
                return None
            raise RuntimeError("Channel receive timed out")

    def try_send(self, value: Any) -> bool:
        if self._closed:
            return False
        try:
            self._queue.put_nowait(value)
            return True
        except queue.Full:
            return False

    def try_receive(self):
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    def size(self) -> int:
        return self._queue.qsize()

    def is_empty(self) -> bool:
        return self._queue.empty()

    def __repr__(self):
        status = "closed" if self._closed else f"size={self.size()}"
        return f"<Channel {status}>"


class EPLSemaphore:
    """Counting semaphore for limiting concurrent access.
    
    Usage: Create sem equal to Semaphore(5).  Note: max 5 concurrent
    """
    def __init__(self, count: int = 1):
        self._sem = threading.Semaphore(count)
        self._max = count

    def acquire(self, timeout: float = None) -> bool:
        return self._sem.acquire(timeout=timeout)

    def release(self):
        self._sem.release()

    def with_permit(self, func: Callable) -> Any:
        self.acquire()
        try:
            return func()
        finally:
            self.release()

    def __repr__(self):
        return f"<Semaphore max={self._max}>"


class EPLAtomicCounter:
    """Thread-safe atomic counter.
    
    Usage: Create counter equal to Atomic(0).
           counter.increment().
           counter.decrement().
           Print counter.get().
    """
    def __init__(self, initial: int = 0):
        self._value = initial
        self._lock = threading.Lock()

    def get(self) -> int:
        with self._lock:
            return self._value

    def set(self, value: int):
        with self._lock:
            self._value = value

    def increment(self, amount: int = 1) -> int:
        with self._lock:
            self._value += amount
            return self._value

    def decrement(self, amount: int = 1) -> int:
        with self._lock:
            self._value -= amount
            return self._value

    def compare_and_swap(self, expected: int, new_value: int) -> bool:
        with self._lock:
            if self._value == expected:
                self._value = new_value
                return True
            return False

    def __repr__(self):
        return f"<Atomic value={self.get()}>"


class EPLThreadPool:
    """Managed thread pool with structured concurrency.
    
    Usage:
        Create pool equal to ThreadPool(4).
        Create future equal to pool.submit(lambda -> compute()).
        Print future.result().
        pool.shutdown().
    """
    def __init__(self, max_workers: int = 4):
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._futures: List[concurrent.futures.Future] = []
        self._max_workers = max_workers

    def submit(self, func: Callable, *args) -> 'EPLFutureWrapper':
        future = self._executor.submit(func, *args)
        self._futures.append(future)
        return EPLFutureWrapper(future)

    def map(self, func: Callable, items: list) -> list:
        futures = [self._executor.submit(func, item) for item in items]
        return [f.result() for f in futures]

    def shutdown(self, wait: bool = True):
        self._executor.shutdown(wait=wait)

    def wait_all(self, timeout: float = None) -> bool:
        done, not_done = concurrent.futures.wait(self._futures, timeout=timeout)
        return len(not_done) == 0

    def __repr__(self):
        return f"<ThreadPool workers={self._max_workers}>"


class EPLFutureWrapper:
    """Wrapper around concurrent.futures.Future for EPL."""
    def __init__(self, future: concurrent.futures.Future):
        self._future = future

    def result(self, timeout: float = None) -> Any:
        return self._future.result(timeout=timeout)

    def is_done(self) -> bool:
        return self._future.done()

    def cancel(self) -> bool:
        return self._future.cancel()

    def is_cancelled(self) -> bool:
        return self._future.cancelled()

    def __repr__(self):
        if self._future.done():
            try:
                return f"<Future done={self._future.result(timeout=0)}>"
            except Exception as e:
                return f"<Future error={e}>"
        return "<Future pending>"


class EPLWaitGroup:
    """WaitGroup for coordinating multiple goroutine-style tasks.
    
    Usage:
        Create wg equal to WaitGroup().
        wg.add(3).
        ... spawn 3 tasks, each calls wg.done() ...
        wg.wait().  Note: blocks until all 3 done
    """
    def __init__(self):
        self._count = 0
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._event.set()

    def add(self, count: int = 1):
        with self._lock:
            self._count += count
            if self._count > 0:
                self._event.clear()

    def done(self):
        with self._lock:
            self._count -= 1
            if self._count <= 0:
                self._count = 0
                self._event.set()

    def wait(self, timeout: float = None) -> bool:
        return self._event.wait(timeout=timeout)

    def __repr__(self):
        return f"<WaitGroup pending={self._count}>"


class EPLTimer:
    """Repeating or one-shot timer."""
    def __init__(self, interval: float, func: Callable, repeat: bool = False):
        self._interval = interval
        self._func = func
        self._repeat = repeat
        self._timer = None
        self._running = False

    def start(self):
        self._running = True
        self._schedule()

    def _schedule(self):
        if not self._running:
            return
        self._timer = threading.Timer(self._interval, self._run)
        self._timer.daemon = True
        self._timer.start()

    def _run(self):
        if not self._running:
            return
        try:
            self._func()
        except Exception as e:
            import sys
            print(f"[EPL Timer] Unhandled exception: {e}", file=sys.stderr)
        if self._repeat and self._running:
            self._schedule()

    def stop(self):
        self._running = False
        if self._timer:
            self._timer.cancel()

    def __repr__(self):
        return f"<Timer interval={self._interval} running={self._running}>"


# ─── EPL Built-in Functions for Concurrency ────────────────

def create_mutex() -> EPLMutex:
    return EPLMutex()

def create_rwlock() -> EPLRWLock:
    return EPLRWLock()

def create_channel(capacity: int = 0) -> EPLChannel:
    return EPLChannel(capacity)

def create_semaphore(count: int = 1) -> EPLSemaphore:
    return EPLSemaphore(count)

def create_atomic(initial: int = 0) -> EPLAtomicCounter:
    return EPLAtomicCounter(initial)

def create_thread_pool(workers: int = 4) -> EPLThreadPool:
    return EPLThreadPool(workers)

def create_wait_group() -> EPLWaitGroup:
    return EPLWaitGroup()

def create_timer(interval: float, func: Callable, repeat: bool = False) -> EPLTimer:
    return EPLTimer(interval, func, repeat)

def parallel_map(func: Callable, items: list, workers: int = 4) -> list:
    """Apply func to each item in parallel using a thread pool."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(func, item) for item in items]
        results = []
        errors = []
        for f in futures:
            try:
                results.append(f.result())
            except Exception as e:
                errors.append(e)
                results.append(None)
        if errors:
            import sys
            for err in errors:
                print(f"[EPL parallel_map] Error: {err}", file=sys.stderr)
        return results

def parallel_for_each(func: Callable, items: list, workers: int = 4):
    """Execute func for each item in parallel, no return."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(func, item) for item in items]
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()  # Propagate exceptions
            except Exception as e:
                import sys
                print(f"[EPL parallel_for_each] Error: {e}", file=sys.stderr)

def sleep_ms(ms: int):
    """Sleep for given milliseconds."""
    time.sleep(ms / 1000.0)
