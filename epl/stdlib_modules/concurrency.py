"""
epl.stdlib_modules.concurrency — Threading and concurrency domain public API.
"""

from __future__ import annotations

FUNCTIONS = frozenset(
    {
        # Basic threading
        'thread_run',
        'thread_sleep',
        'atomic_counter',
        'mutex_create',
        'mutex_lock',
        'mutex_unlock',
        # RW locks
        'rwlock_create',
        'rwlock_read_lock',
        'rwlock_read_unlock',
        'rwlock_write_lock',
        'rwlock_write_unlock',
        # Channels
        'channel_create',
        'channel_send',
        'channel_receive',
        'channel_try_send',
        'channel_try_receive',
        'channel_close',
        # Semaphores & atomics
        'semaphore_create',
        'semaphore_acquire',
        'semaphore_release',
        'atomic_create',
        'atomic_get',
        'atomic_set',
        'atomic_increment',
        'atomic_decrement',
        'atomic_cas',
        # Thread pools
        'thread_pool_create',
        'thread_pool_submit',
        'thread_pool_map',
        'thread_pool_shutdown',
        'thread_pool_wait',
        # WaitGroups
        'wait_group_create',
        'wait_group_add',
        'wait_group_done',
        'wait_group_wait',
        # Parallel helpers
        'parallel_map',
        'parallel_for_each',
        'sleep_ms',
        # Real concurrency (OS-level)
        'real_thread_run',
        'real_thread_join',
        'real_thread_is_alive',
        'real_thread_pool_create',
        'real_thread_pool_submit',
        'real_thread_pool_map',
        'real_thread_pool_shutdown',
        'real_mutex_create',
        'real_mutex_lock',
        'real_mutex_unlock',
        'real_semaphore_create',
        'real_semaphore_acquire',
        'real_semaphore_release',
        'real_channel_create',
        'real_channel_send',
        'real_channel_receive',
        'real_channel_try_send',
        'real_channel_try_receive',
        'real_channel_close',
        'real_sleep',
        'real_sleep_ms',
        'real_parallel_map',
        'real_parallel_for_each',
        'real_timer',
        'real_interval',
        'real_interval_stop',
    }
)

DOCS: dict[str, str] = {
    'thread_run': 'Run a function in a background thread.',
    'mutex_create': 'Create a mutual exclusion lock.',
    'mutex_lock': 'Acquire the lock (blocking).',
    'mutex_unlock': 'Release the lock.',
    'channel_create': 'Create a thread-safe message channel.',
    'channel_send': 'Send a value into a channel.',
    'channel_receive': 'Receive a value from a channel (blocking).',
    'channel_try_send': 'Try to send without blocking (returns bool).',
    'channel_try_receive': 'Try to receive without blocking.',
    'semaphore_create': 'Create a counting semaphore.',
    'semaphore_acquire': 'Acquire the semaphore.',
    'semaphore_release': 'Release the semaphore.',
    'thread_pool_create': 'Create a fixed-size thread pool.',
    'thread_pool_submit': 'Submit a task to the pool.',
    'thread_pool_map': 'Map a function over a list using the pool.',
    'thread_pool_wait': 'Wait for all submitted tasks to complete.',
    'parallel_map': 'Apply a function to a list in parallel.',
    'parallel_for_each': 'Run a side-effect for each element in parallel.',
    'sleep_ms': 'Sleep for N milliseconds.',
    'wait_group_create': 'Create a WaitGroup for goroutine-style sync.',
    'wait_group_add': 'Add N to the WaitGroup counter.',
    'wait_group_done': 'Decrement the WaitGroup counter by 1.',
    'wait_group_wait': 'Block until WaitGroup reaches zero.',
    'real_timer': 'Run a function after a delay (real OS timer).',
    'real_interval': 'Run a function repeatedly at an interval.',
    'real_interval_stop': 'Stop a running interval.',
}


def get_functions() -> frozenset[str]:
    return FUNCTIONS


def describe(fn_name: str) -> str:
    return DOCS.get(fn_name, f'{fn_name}: no documentation available.')
