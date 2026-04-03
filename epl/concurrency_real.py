"""
EPL Concurrency Module v2.0
============================
Real threading and process management using Python's
threading, multiprocessing, and concurrent.futures.

Provides:
- Thread creation and management
- Thread pools with work queues
- Mutex/RWLock/Semaphore synchronization
- Channels for thread communication  
- Process spawning and management
- Atomic operations
- Parallel map/filter/reduce
- Wait groups for synchronization
- Timer and interval scheduling
"""

import threading
import multiprocessing
import concurrent.futures
import queue
import time
import os
import subprocess
import signal
from typing import Any, Optional, Callable
from dataclasses import dataclass


# ─── Thread ───────────────────────────────────────────────────

class EPLThread:
    """
    Real thread wrapper.
    
    Usage from EPL:
        Set t To Thread(Given Do
            Print "Running in thread"
        EndGiven)
        t.start()
        t.join()
    """

    _counter = 0
    _counter_lock = threading.Lock()

    def __init__(self, target: Callable = None, args: tuple = (),
                 name: str = None, daemon: bool = False):
        with EPLThread._counter_lock:
            EPLThread._counter += 1
            self._id = EPLThread._counter

        self._name = name or f"EPLThread-{self._id}"
        self._target = target
        self._args = args
        self._result = None
        self._error = None
        self._thread = threading.Thread(
            target=self._run, name=self._name, daemon=daemon
        )
        self._started = False
        self._finished = False

    def _run(self):
        try:
            if self._target:
                self._result = self._target(*self._args)
        except Exception as e:
            self._error = e
        finally:
            self._finished = True

    def start(self):
        """Start the thread."""
        if not self._started:
            self._started = True
            self._thread.start()
        return self

    def join(self, timeout: float = None):
        """Wait for thread to complete."""
        self._thread.join(timeout)
        if self._error:
            raise self._error
        return self._result

    @property
    def result(self):
        return self._result

    @property
    def error(self):
        return self._error

    @property
    def is_alive(self) -> bool:
        return self._thread.is_alive()

    @property
    def is_finished(self) -> bool:
        return self._finished

    @property
    def name(self) -> str:
        return self._name

    @property
    def id(self) -> int:
        return self._id

    def __repr__(self):
        status = "alive" if self.is_alive else ("finished" if self._finished else "created")
        return f"<Thread '{self._name}' {status}>"


# ─── Thread Pool ──────────────────────────────────────────────

class ThreadPool:
    """
    Thread pool for parallel task execution.
    
    Usage from EPL:
        Set pool To ThreadPool(4)
        Set future To pool.submit(my_function, arg1, arg2)
        Set result To future.result()
        pool.shutdown()
    """

    def __init__(self, max_workers: int = None):
        self._max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_workers
        )

    def submit(self, fn: Callable, *args) -> 'Future':
        """Submit a task and return a Future."""
        future = self._executor.submit(fn, *args)
        return Future(future)

    def map(self, fn: Callable, items: list, timeout: float = None) -> list:
        """Apply function to all items in parallel."""
        results = list(self._executor.map(fn, items, timeout=timeout))
        return results

    def shutdown(self, wait: bool = True):
        """Shutdown the pool."""
        self._executor.shutdown(wait=wait)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.shutdown()


class Future:
    """Wraps a concurrent.futures.Future."""

    def __init__(self, future: concurrent.futures.Future):
        self._future = future

    def result(self, timeout: float = None):
        return self._future.result(timeout=timeout)

    @property
    def done(self) -> bool:
        return self._future.done()

    @property
    def cancelled(self) -> bool:
        return self._future.cancelled()

    def cancel(self) -> bool:
        return self._future.cancel()

    def add_callback(self, fn: Callable):
        self._future.add_done_callback(lambda f: fn(f.result()))

    def __repr__(self):
        return f"<Future done={self.done}>"


# ─── Synchronization Primitives ───────────────────────────────

class Mutex:
    """
    Mutual exclusion lock.
    
    Usage from EPL:
        Set lock To Mutex()
        lock.acquire()
        // critical section
        lock.release()
        
        // Or with context manager style:
        lock.with(Given Do
            // critical section
        EndGiven)
    """

    def __init__(self):
        self._lock = threading.Lock()

    def acquire(self, timeout: float = -1) -> bool:
        return self._lock.acquire(timeout=timeout)

    def release(self):
        self._lock.release()

    def locked(self) -> bool:
        return self._lock.locked()

    def with_lock(self, fn: Callable):
        """Execute function while holding the lock."""
        with self._lock:
            return fn()

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, *args):
        self._lock.release()


class RWLock:
    """Read-write lock allowing multiple readers or one writer."""

    def __init__(self):
        self._read_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._readers = 0

    def acquire_read(self):
        with self._read_lock:
            self._readers += 1
            if self._readers == 1:
                self._write_lock.acquire()

    def release_read(self):
        with self._read_lock:
            self._readers -= 1
            if self._readers == 0:
                self._write_lock.release()

    def acquire_write(self):
        self._write_lock.acquire()

    def release_write(self):
        self._write_lock.release()


class Semaphore:
    """Counting semaphore."""

    def __init__(self, count: int = 1):
        self._semaphore = threading.Semaphore(count)

    def acquire(self, timeout: float = None) -> bool:
        return self._semaphore.acquire(timeout=timeout)

    def release(self):
        self._semaphore.release()

    def __enter__(self):
        self._semaphore.acquire()
        return self

    def __exit__(self, *args):
        self._semaphore.release()


class Barrier:
    """Thread barrier - all threads wait until N arrive."""

    def __init__(self, parties: int):
        self._barrier = threading.Barrier(parties)

    def wait(self, timeout: float = None):
        return self._barrier.wait(timeout=timeout)

    def reset(self):
        self._barrier.reset()

    @property
    def parties(self):
        return self._barrier.parties

    @property
    def n_waiting(self):
        return self._barrier.n_waiting


class Event:
    """Thread event for signaling."""

    def __init__(self):
        self._event = threading.Event()

    def set(self):
        self._event.set()

    def clear(self):
        self._event.clear()

    def wait(self, timeout: float = None) -> bool:
        return self._event.wait(timeout=timeout)

    @property
    def is_set(self) -> bool:
        return self._event.is_set()


# ─── Channel ─────────────────────────────────────────────────

class Channel:
    """
    Thread-safe communication channel (like Go channels).
    
    Usage from EPL:
        Set ch To Channel(10)  // buffered channel
        ch.send("hello")
        Set msg To ch.receive()
    """

    def __init__(self, capacity: int = 0):
        if capacity <= 0:
            self._queue = queue.Queue()
        else:
            self._queue = queue.Queue(maxsize=capacity)
        self._closed = False

    def send(self, value, timeout: float = None):
        """Send a value to the channel."""
        if self._closed:
            raise RuntimeError("Cannot send on closed channel")
        self._queue.put(value, timeout=timeout)

    def receive(self, timeout: float = None):
        """Receive a value from the channel."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            if self._closed:
                return None
            raise TimeoutError("Channel receive timed out")

    def try_send(self, value) -> bool:
        """Non-blocking send. Returns True if sent."""
        try:
            self._queue.put_nowait(value)
            return True
        except queue.Full:
            return False

    def try_receive(self):
        """Non-blocking receive. Returns (value, True) or (None, False)."""
        try:
            return self._queue.get_nowait(), True
        except queue.Empty:
            return None, False

    def close(self):
        self._closed = True

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def size(self) -> int:
        return self._queue.qsize()

    @property
    def is_empty(self) -> bool:
        return self._queue.empty()

    def __iter__(self):
        """Iterate over channel values until closed."""
        while not self._closed or not self._queue.empty():
            try:
                yield self._queue.get(timeout=0.1)
            except queue.Empty:
                if self._closed:
                    break


# ─── Atomic Operations ────────────────────────────────────────

class AtomicInt:
    """Thread-safe integer with atomic operations."""

    def __init__(self, value: int = 0):
        self._value = value
        self._lock = threading.Lock()

    def get(self) -> int:
        with self._lock:
            return self._value

    def set(self, value: int):
        with self._lock:
            self._value = value

    def increment(self, delta: int = 1) -> int:
        with self._lock:
            self._value += delta
            return self._value

    def decrement(self, delta: int = 1) -> int:
        with self._lock:
            self._value -= delta
            return self._value

    def compare_and_swap(self, expected: int, new_value: int) -> bool:
        with self._lock:
            if self._value == expected:
                self._value = new_value
                return True
            return False

    @property
    def value(self) -> int:
        return self.get()

    def __repr__(self):
        return f"<AtomicInt value={self.get()}>"


class AtomicBool:
    """Thread-safe boolean."""

    def __init__(self, value: bool = False):
        self._value = value
        self._lock = threading.Lock()

    def get(self) -> bool:
        with self._lock:
            return self._value

    def set(self, value: bool):
        with self._lock:
            self._value = value

    def toggle(self) -> bool:
        with self._lock:
            self._value = not self._value
            return self._value


# ─── Wait Group ───────────────────────────────────────────────

class WaitGroup:
    """
    Wait for a collection of tasks to finish (like Go's sync.WaitGroup).
    
    Usage from EPL:
        Set wg To WaitGroup()
        wg.add(3)
        // spawn 3 tasks that call wg.done() when finished
        wg.wait()  // blocks until all 3 call done()
    """

    def __init__(self):
        self._counter = 0
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._event.set()

    def add(self, count: int = 1):
        with self._lock:
            self._counter += count
            if self._counter > 0:
                self._event.clear()

    def done(self):
        with self._lock:
            self._counter -= 1
            if self._counter <= 0:
                self._counter = 0
                self._event.set()

    def wait(self, timeout: float = None):
        return self._event.wait(timeout=timeout)

    @property
    def count(self) -> int:
        with self._lock:
            return self._counter


# ─── Process Management ──────────────────────────────────────

class Process:
    """
    Spawn and manage OS processes.
    
    Usage from EPL:
        Set p To Process("python", ["-c", "print('hello')"])
        p.start()
        Set output To p.wait()
        Print output.stdout
    """

    def __init__(self, command: str, args: list = None, cwd: str = None,
                 env: dict = None, shell: bool = False):
        self.command = command
        self.args = args or []
        self.cwd = cwd
        self.env = env
        self.shell = shell
        self._process: Optional[subprocess.Popen] = None
        self._stdout = None
        self._stderr = None
        self._exit_code = None

    def start(self):
        """Start the process."""
        cmd = [self.command] + self.args if not self.shell else self.command
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
            env=self.env,
            shell=self.shell,
        )
        return self

    def wait(self, timeout: float = None) -> 'ProcessResult':
        """Wait for process to complete and return result."""
        if not self._process:
            self.start()
        stdout, stderr = self._process.communicate(timeout=timeout)
        self._stdout = stdout.decode('utf-8', errors='replace')
        self._stderr = stderr.decode('utf-8', errors='replace')
        self._exit_code = self._process.returncode
        return ProcessResult(self._exit_code, self._stdout, self._stderr)

    def kill(self):
        """Kill the process."""
        if self._process:
            self._process.kill()

    def terminate(self):
        """Terminate the process gracefully."""
        if self._process:
            self._process.terminate()

    def send_input(self, data: str):
        """Send data to process stdin."""
        if self._process and self._process.stdin:
            self._process.stdin.write(data.encode())
            self._process.stdin.flush()

    @property
    def pid(self) -> Optional[int]:
        return self._process.pid if self._process else None

    @property
    def is_alive(self) -> bool:
        if self._process:
            return self._process.poll() is None
        return False

    @property
    def exit_code(self) -> Optional[int]:
        if self._process:
            return self._process.poll()
        return self._exit_code

    def __repr__(self):
        return f"<Process cmd='{self.command}' pid={self.pid}>"


@dataclass
class ProcessResult:
    """Result of a completed process."""
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def __repr__(self):
        return f"<ProcessResult code={self.exit_code}>"


# ─── Timer and Interval ──────────────────────────────────────

class Timer:
    """Execute a function after a delay."""

    def __init__(self, delay: float, fn: Callable, args: tuple = ()):
        self._timer = threading.Timer(delay, fn, args=args)
        self._timer.daemon = True

    def start(self):
        self._timer.start()
        return self

    def cancel(self):
        self._timer.cancel()


class Interval:
    """Execute a function repeatedly at fixed intervals."""

    def __init__(self, interval: float, fn: Callable, args: tuple = ()):
        self._interval = interval
        self._fn = fn
        self._args = args
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self):
        while self._running:
            time.sleep(self._interval)
            if self._running:
                try:
                    self._fn(*self._args)
                except Exception:
                    pass

    def stop(self):
        self._running = False


# ─── Parallel Operations ─────────────────────────────────────

def parallel_map(fn: Callable, items: list, max_workers: int = None) -> list:
    """Apply function to items in parallel using thread pool."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(fn, items))


def parallel_for_each(fn: Callable, items: list, max_workers: int = None):
    """Execute function for each item in parallel."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fn, item) for item in items]
        concurrent.futures.wait(futures)
        # Raise first exception if any
        for f in futures:
            if f.exception():
                raise f.exception()


def parallel_filter(fn: Callable, items: list, max_workers: int = None) -> list:
    """Filter items in parallel."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(lambda x: (x, fn(x)), items))
        return [item for item, keep in results if keep]


def race(*tasks) -> Any:
    """Run tasks in parallel, return first result."""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(task) for task in tasks]
        done, _ = concurrent.futures.wait(
            futures, return_when=concurrent.futures.FIRST_COMPLETED
        )
        return done.pop().result()


def all_settled(*tasks) -> list:
    """Run all tasks, return list of (result, error) tuples in submission order."""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(task) for task in tasks]
        results = []
        for f in futures:  # preserve submission order
            try:
                results.append((f.result(), None))
            except Exception as e:
                results.append((None, e))
        return results


# ─── Convenience Functions ────────────────────────────────────

def run_in_thread(fn: Callable, *args) -> EPLThread:
    """Quick way to run a function in a new thread."""
    t = EPLThread(target=fn, args=args, daemon=True)
    t.start()
    return t


def sleep(seconds: float):
    """Sleep for specified seconds."""
    time.sleep(seconds)


def sleep_ms(milliseconds: int):
    """Sleep for specified milliseconds."""
    time.sleep(milliseconds / 1000.0)


def cpu_count() -> int:
    """Get number of CPU cores."""
    return os.cpu_count() or 1


def current_thread_name() -> str:
    """Get current thread name."""
    return threading.current_thread().name


def active_thread_count() -> int:
    """Get number of active threads."""
    return threading.active_count()


def run_command(command: str, shell: bool = True, timeout: float = None) -> ProcessResult:
    """Run a shell command and return result."""
    try:
        result = subprocess.run(
            command, shell=shell, capture_output=True, text=True,
            timeout=timeout
        )
        return ProcessResult(result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return ProcessResult(-1, "", "Command timed out")
