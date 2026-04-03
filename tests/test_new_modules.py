"""
Tests for EPL v3.0 new modules:
  - database_real (Real SQLite)
  - networking (TCP/UDP/HTTP)
  - concurrency_real (Threading, channels, atomics)
  - vm (Bytecode VM)
  - packager (Cross-platform packaging)
  - stdlib integration (all wired functions)
"""

import sys
import os
import time
import threading
import tempfile
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.stdlib import call_stdlib, STDLIB_FUNCTIONS
from epl.interpreter import EPLDict

# ═══════════════════════════════════════════════════════════
#  Test Infrastructure
# ═══════════════════════════════════════════════════════════

RESULTS = {"passed": 0, "failed": 0, "errors": []}


def test(name, fn):
    """Run a test function and record results."""
    try:
        fn()
        RESULTS["passed"] += 1
        print(f"  PASS: {name}")
    except AssertionError as e:
        RESULTS["failed"] += 1
        RESULTS["errors"].append((name, str(e)))
        print(f"  FAIL: {name} — {e}")
    except Exception as e:
        RESULTS["failed"] += 1
        RESULTS["errors"].append((name, f"ERROR: {e}"))
        print(f"  ERROR: {name} — {e}")




test.__test__ = False

def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}. {msg}")


def assert_true(val, msg=""):
    if not val:
        raise AssertionError(f"Expected truthy, got {val!r}. {msg}")


def assert_false(val, msg=""):
    if val:
        raise AssertionError(f"Expected falsy, got {val!r}. {msg}")


def assert_in(item, container, msg=""):
    if item not in container:
        raise AssertionError(f"{item!r} not in {container!r}. {msg}")


def assert_gt(a, b, msg=""):
    if not (a > b):
        raise AssertionError(f"Expected {a} > {b}. {msg}")


def assert_isinstance(obj, cls, msg=""):
    if not isinstance(obj, cls):
        raise AssertionError(f"Expected {cls.__name__}, got {type(obj).__name__}. {msg}")


# ═══════════════════════════════════════════════════════════
#  I. STDLIB Integration Tests
# ═══════════════════════════════════════════════════════════

def test_stdlib_has_new_functions():
    """Verify all new function groups are registered."""
    def run():
        new_prefixes = ['real_db_', 'real_thread_', 'real_mutex_', 'real_rwlock_',
                        'real_semaphore_', 'real_barrier_', 'real_event_',
                        'real_channel_', 'real_atomic_', 'real_waitgroup_',
                        'real_parallel_', 'real_sleep', 'real_cpu_',
                        'real_process_', 'real_timer', 'real_interval',
                        'net_', 'vm_']
        for prefix in new_prefixes:
            matches = [f for f in STDLIB_FUNCTIONS if f.startswith(prefix)]
            assert_true(len(matches) > 0, f"No functions with prefix '{prefix}'")
        # Total should be > 300
        assert_gt(len(STDLIB_FUNCTIONS), 300, "Expected > 300 stdlib functions")
    test("stdlib_has_new_functions", run)


# ═══════════════════════════════════════════════════════════
#  II. Real Database Tests
# ═══════════════════════════════════════════════════════════

def test_db_connect_close():
    def run():
        db = call_stdlib('real_db_connect', [':memory:', 'test_conn'], 0)
        assert_eq(db, 'test_conn')
        call_stdlib('real_db_close', ['test_conn'], 0)
    test("db_connect_close", run)


def test_db_create_table_and_insert():
    def run():
        db = call_stdlib('real_db_connect', [':memory:', 'test_crud'], 0)
        cols = EPLDict({'name': 'TEXT', 'age': 'INTEGER', 'email': 'TEXT'})
        call_stdlib('real_db_create_table', [db, 'users', cols], 0)

        record = EPLDict({'name': 'Alice', 'age': 30, 'email': 'alice@test.com'})
        row_id = call_stdlib('real_db_insert', [db, 'users', record], 0)
        assert_eq(row_id, 1)

        record2 = EPLDict({'name': 'Bob', 'age': 25, 'email': 'bob@test.com'})
        row_id2 = call_stdlib('real_db_insert', [db, 'users', record2], 0)
        assert_eq(row_id2, 2)

        call_stdlib('real_db_close', [db], 0)
    test("db_create_table_and_insert", run)


def test_db_query_and_query_one():
    def run():
        db = call_stdlib('real_db_connect', [':memory:', 'test_query'], 0)
        cols = EPLDict({'name': 'TEXT', 'score': 'INTEGER'})
        call_stdlib('real_db_create_table', [db, 'scores', cols], 0)

        call_stdlib('real_db_insert', [db, 'scores', EPLDict({'name': 'A', 'score': 100})], 0)
        call_stdlib('real_db_insert', [db, 'scores', EPLDict({'name': 'B', 'score': 85})], 0)
        call_stdlib('real_db_insert', [db, 'scores', EPLDict({'name': 'C', 'score': 92})], 0)

        rows = call_stdlib('real_db_query', [db, 'SELECT * FROM scores ORDER BY score DESC'], 0)
        assert_eq(len(rows), 3)

        one = call_stdlib('real_db_query_one', [db, 'SELECT * FROM scores WHERE name=?', ['B']], 0)
        assert_true(one is not None)

        call_stdlib('real_db_close', [db], 0)
    test("db_query_and_query_one", run)


def test_db_update_and_delete():
    def run():
        db = call_stdlib('real_db_connect', [':memory:', 'test_upd'], 0)
        cols = EPLDict({'name': 'TEXT', 'val': 'INTEGER'})
        call_stdlib('real_db_create_table', [db, 'items', cols], 0)
        call_stdlib('real_db_insert', [db, 'items', EPLDict({'name': 'x', 'val': 1})], 0)
        call_stdlib('real_db_insert', [db, 'items', EPLDict({'name': 'y', 'val': 2})], 0)

        call_stdlib('real_db_update', [db, 'items', EPLDict({'val': 99}), EPLDict({'name': 'x'})], 0)
        one = call_stdlib('real_db_query_one', [db, 'SELECT val FROM items WHERE name=?', ['x']], 0)
        assert_true(one is not None)

        call_stdlib('real_db_delete', [db, 'items', EPLDict({'name': 'y'})], 0)
        count = call_stdlib('real_db_count', [db, 'items'], 0)
        assert_eq(count, 1)

        call_stdlib('real_db_close', [db], 0)
    test("db_update_and_delete", run)


def test_db_find_by_id():
    def run():
        db = call_stdlib('real_db_connect', [':memory:', 'test_find'], 0)
        cols = EPLDict({'id': 'INTEGER PRIMARY KEY AUTOINCREMENT', 'name': 'TEXT'})
        call_stdlib('real_db_create_table', [db, 'people', cols], 0)
        call_stdlib('real_db_insert', [db, 'people', EPLDict({'name': 'Alice'})], 0)
        call_stdlib('real_db_insert', [db, 'people', EPLDict({'name': 'Bob'})], 0)

        row = call_stdlib('real_db_find_by_id', [db, 'people', 2], 0)
        assert_true(row is not None)

        call_stdlib('real_db_close', [db], 0)
    test("db_find_by_id", run)


def test_db_table_exists():
    def run():
        db = call_stdlib('real_db_connect', [':memory:', 'test_exists'], 0)
        assert_false(call_stdlib('real_db_table_exists', [db, 'nonexistent'], 0))
        cols = EPLDict({'x': 'TEXT'})
        call_stdlib('real_db_create_table', [db, 'real_table', cols], 0)
        assert_true(call_stdlib('real_db_table_exists', [db, 'real_table'], 0))
        call_stdlib('real_db_close', [db], 0)
    test("db_table_exists", run)


def test_db_transactions():
    def run():
        db = call_stdlib('real_db_connect', [':memory:', 'test_txn'], 0)
        cols = EPLDict({'val': 'INTEGER'})
        call_stdlib('real_db_create_table', [db, 'txn_test', cols], 0)
        call_stdlib('real_db_insert', [db, 'txn_test', EPLDict({'val': 1})], 0)

        call_stdlib('real_db_begin', [db], 0)
        call_stdlib('real_db_insert', [db, 'txn_test', EPLDict({'val': 2})], 0)
        call_stdlib('real_db_commit', [db], 0)

        count = call_stdlib('real_db_count', [db, 'txn_test'], 0)
        assert_eq(count, 2)

        call_stdlib('real_db_close', [db], 0)
    test("db_transactions", run)


def test_db_model_crud():
    def run():
        db = call_stdlib('real_db_connect', [':memory:', 'test_model'], 0)
        fields = EPLDict({'name': 'TEXT NOT NULL', 'age': 'INTEGER DEFAULT 0'})
        call_stdlib('real_db_model_define', [db, 'person', fields], 0)

        result = call_stdlib('real_db_model_create', [db, 'person', EPLDict({'name': 'Alice', 'age': 30})], 0)
        assert_true(result is not None)

        call_stdlib('real_db_model_create', [db, 'person', EPLDict({'name': 'Bob', 'age': 25})], 0)

        all_records = call_stdlib('real_db_model_all', [db, 'person'], 0)
        assert_eq(len(all_records), 2)

        count = call_stdlib('real_db_model_count', [db, 'person'], 0)
        assert_eq(count, 2)

        first = call_stdlib('real_db_model_first', [db, 'person'], 0)
        assert_true(first is not None)

        call_stdlib('real_db_close', [db], 0)
    test("db_model_crud", run)


# ═══════════════════════════════════════════════════════════
#  III. Concurrency Tests
# ═══════════════════════════════════════════════════════════

def test_mutex_lock_unlock():
    def run():
        mid = call_stdlib('real_mutex_create', [], 0)
        assert_true(mid.startswith('mtx_'))
        call_stdlib('real_mutex_lock', [mid], 0)
        call_stdlib('real_mutex_unlock', [mid], 0)
    test("mutex_lock_unlock", run)


def test_atomic_int_operations():
    def run():
        aid = call_stdlib('real_atomic_int', [0], 0)
        assert_eq(call_stdlib('real_atomic_int_get', [aid], 0), 0)

        call_stdlib('real_atomic_int_set', [aid, 42], 0)
        assert_eq(call_stdlib('real_atomic_int_get', [aid], 0), 42)

        result = call_stdlib('real_atomic_int_inc', [aid, 8], 0)
        assert_eq(result, 50)

        result = call_stdlib('real_atomic_int_dec', [aid, 10], 0)
        assert_eq(result, 40)

        # CAS
        ok = call_stdlib('real_atomic_int_cas', [aid, 40, 100], 0)
        assert_true(ok)
        assert_eq(call_stdlib('real_atomic_int_get', [aid], 0), 100)

        # CAS fail
        ok = call_stdlib('real_atomic_int_cas', [aid, 999, 0], 0)
        assert_false(ok)
        assert_eq(call_stdlib('real_atomic_int_get', [aid], 0), 100)
    test("atomic_int_operations", run)


def test_atomic_bool_operations():
    def run():
        aid = call_stdlib('real_atomic_bool', [False], 0)
        assert_false(call_stdlib('real_atomic_bool_get', [aid], 0))

        call_stdlib('real_atomic_bool_set', [aid, True], 0)
        assert_true(call_stdlib('real_atomic_bool_get', [aid], 0))

        call_stdlib('real_atomic_bool_toggle', [aid], 0)
        assert_false(call_stdlib('real_atomic_bool_get', [aid], 0))
    test("atomic_bool_operations", run)


def test_channel_send_receive():
    def run():
        ch = call_stdlib('real_channel_create', [5], 0)
        call_stdlib('real_channel_send', [ch, 'hello'], 0)
        call_stdlib('real_channel_send', [ch, 'world'], 0)

        val1 = call_stdlib('real_channel_receive', [ch], 0)
        assert_eq(val1, 'hello')
        val2 = call_stdlib('real_channel_receive', [ch], 0)
        assert_eq(val2, 'world')

        # try_send / try_receive
        ok = call_stdlib('real_channel_try_send', [ch, 42], 0)
        assert_true(ok)
        val = call_stdlib('real_channel_try_receive', [ch], 0)
        # try_receive returns (value, True) tuple or (None, False)
        if isinstance(val, tuple):
            assert_eq(val[0], 42)
        else:
            assert_eq(val, 42)

        call_stdlib('real_channel_close', [ch], 0)
    test("channel_send_receive", run)


def test_event_set_wait():
    def run():
        eid = call_stdlib('real_event_create', [], 0)
        assert_false(call_stdlib('real_event_is_set', [eid], 0))
        call_stdlib('real_event_set', [eid], 0)
        assert_true(call_stdlib('real_event_is_set', [eid], 0))
        result = call_stdlib('real_event_wait', [eid, 1.0], 0)
        assert_true(result)
        call_stdlib('real_event_clear', [eid], 0)
        assert_false(call_stdlib('real_event_is_set', [eid], 0))
    test("event_set_wait", run)


def test_semaphore_acquire_release():
    def run():
        sid = call_stdlib('real_semaphore_create', [2], 0)
        call_stdlib('real_semaphore_acquire', [sid], 0)
        call_stdlib('real_semaphore_acquire', [sid], 0)
        # Now at capacity — release one
        call_stdlib('real_semaphore_release', [sid], 0)
        call_stdlib('real_semaphore_release', [sid], 0)
    test("semaphore_acquire_release", run)


def test_waitgroup():
    def run():
        wg = call_stdlib('real_waitgroup_create', [], 0)
        call_stdlib('real_waitgroup_add', [wg, 3], 0)
        call_stdlib('real_waitgroup_done', [wg], 0)
        call_stdlib('real_waitgroup_done', [wg], 0)
        call_stdlib('real_waitgroup_done', [wg], 0)
        result = call_stdlib('real_waitgroup_wait', [wg, 1.0], 0)
        assert_true(result)
    test("waitgroup", run)


def test_cpu_count():
    def run():
        cpus = call_stdlib('real_cpu_count', [], 0)
        assert_gt(cpus, 0)
    test("cpu_count", run)


def test_current_thread():
    def run():
        name = call_stdlib('real_current_thread', [], 0)
        assert_isinstance(name, str)
        assert_true(len(name) > 0)
    test("current_thread", run)


def test_active_threads():
    def run():
        count = call_stdlib('real_active_threads', [], 0)
        assert_gt(count, 0)
    test("active_threads", run)


def test_sleep_ms():
    def run():
        start = time.time()
        call_stdlib('real_sleep_ms', [50], 0)
        elapsed = time.time() - start
        assert_gt(elapsed, 0.03)  # at least 30ms
    test("sleep_ms", run)


def test_process_run():
    def run():
        result = call_stdlib('real_process_run', ['python -c "print(42)"'], 0)
        assert_true(result is not None)
    test("process_run", run)


def test_rwlock():
    def run():
        rid = call_stdlib('real_rwlock_create', [], 0)
        call_stdlib('real_rwlock_read_lock', [rid], 0)
        call_stdlib('real_rwlock_read_unlock', [rid], 0)
        call_stdlib('real_rwlock_write_lock', [rid], 0)
        call_stdlib('real_rwlock_write_unlock', [rid], 0)
    test("rwlock", run)


def test_barrier():
    def run():
        bid = call_stdlib('real_barrier_create', [1], 0)
        # With parties=1, a single wait should pass
        call_stdlib('real_barrier_wait', [bid], 0)
        call_stdlib('real_barrier_reset', [bid], 0)
    test("barrier", run)


# ═══════════════════════════════════════════════════════════
#  IV. Networking Tests
# ═══════════════════════════════════════════════════════════

def test_dns_lookup():
    def run():
        ip = call_stdlib('net_dns_lookup', ['localhost'], 0)
        assert_in(ip, ['127.0.0.1', '::1'])
    test("dns_lookup", run)


def test_hostname():
    def run():
        name = call_stdlib('net_hostname', [], 0)
        assert_true(len(name) > 0)
    test("hostname", run)


def test_local_ip():
    def run():
        ip = call_stdlib('net_local_ip', [], 0)
        assert_true('.' in ip or ':' in ip)
    test("local_ip", run)


def test_is_port_open():
    def run():
        # Port 1 should be closed on localhost
        result = call_stdlib('net_is_port_open', ['127.0.0.1', 1, 0.5], 0)
        assert_false(result)
    test("is_port_open", run)


def test_udp_socket_create_close():
    def run():
        sid = call_stdlib('net_udp_socket', [], 0)
        assert_true(sid.startswith('nudp_'))
        call_stdlib('net_udp_close', [sid], 0)
    test("udp_socket_create_close", run)


def test_http_client_create():
    def run():
        cid = call_stdlib('net_http_client', ['https://httpbin.org', 10], 0)
        assert_true(cid.startswith('httpc_'))
    test("http_client_create", run)


# ═══════════════════════════════════════════════════════════
#  V. Bytecode VM Tests
# ═══════════════════════════════════════════════════════════

def test_vm_run():
    def run():
        result = call_stdlib('vm_run', ['set x to 42.\nshow x.'], 0)
        assert_true(result is not None)
    test("vm_run", run)


def test_vm_compile():
    def run():
        result = call_stdlib('vm_compile', ['set x to 10.'], 0)
        assert_true(result is not None)
    test("vm_compile", run)


def test_vm_disassemble():
    def run():
        disasm = call_stdlib('vm_disassemble', ['set x to 5.'], 0)
        assert_isinstance(disasm, str)
        assert_true(len(disasm) > 0)
    test("vm_disassemble", run)


# ═══════════════════════════════════════════════════════════
#  VI. Direct Module Tests (bypass stdlib)
# ═══════════════════════════════════════════════════════════

def test_database_real_direct():
    def run():
        from epl.database_real import db_connect, db_close
        db = db_connect(':memory:', 'direct_test')
        db.create_table('items', {'name': 'TEXT', 'qty': 'INTEGER'})
        db.insert('items', {'name': 'Widget', 'qty': 100})
        db.insert('items', {'name': 'Gadget', 'qty': 50})
        rows = db.query('SELECT * FROM items ORDER BY qty')
        assert_eq(len(rows), 2)
        assert_eq(rows[0]['name'], 'Gadget')
        count = db.count('items')
        assert_eq(count, 2)
        db_close('direct_test')
    test("database_real_direct", run)


def test_database_real_query_builder():
    def run():
        from epl.database_real import db_connect, db_close
        db = db_connect(':memory:', 'qb_test')
        db.create_table('products', {'name': 'TEXT', 'price': 'REAL', 'category': 'TEXT'})
        db.insert('products', {'name': 'A', 'price': 10.0, 'category': 'x'})
        db.insert('products', {'name': 'B', 'price': 20.0, 'category': 'y'})
        db.insert('products', {'name': 'C', 'price': 15.0, 'category': 'x'})

        results = db.table('products').where_eq('category', 'x').order_by('price').get()
        assert_eq(len(results), 2)
        assert_eq(results[0]['name'], 'A')

        total = db.table('products').count()
        assert_eq(total, 3)

        db_close('qb_test')
    test("database_real_query_builder", run)


def test_database_real_model():
    def run():
        from epl.database_real import db_connect, db_close, Model
        db = db_connect(':memory:', 'model_test')
        User = Model(db, 'users', {'name': 'TEXT NOT NULL', 'email': 'TEXT', 'active': 'INTEGER DEFAULT 1'})

        User.create({'name': 'Alice', 'email': 'a@b.com'})
        User.create({'name': 'Bob', 'email': 'b@b.com'})

        all_users = User.all()
        assert_eq(len(all_users), 2)

        alice = User.find(1)
        assert_eq(alice['name'], 'Alice')

        User.update_record(1, {'email': 'alice@new.com'})
        alice = User.find(1)
        assert_eq(alice['email'], 'alice@new.com')

        User.delete_record(2)
        assert_eq(User.count(), 1)

        db_close('model_test')
    test("database_real_model", run)


def test_concurrency_real_thread():
    def run():
        from epl.concurrency_real import run_in_thread
        results = []
        def worker(val):
            results.append(val * 2)
            return val * 2

        t = run_in_thread(worker, 21)
        t.join(5.0)
        assert_eq(t.result, 42)
        assert_true(t.is_finished)
    test("concurrency_real_thread", run)


def test_concurrency_real_parallel_map():
    def run():
        from epl.concurrency_real import parallel_map
        results = parallel_map(lambda x: x ** 2, [1, 2, 3, 4, 5])
        assert_eq(results, [1, 4, 9, 16, 25])
    test("concurrency_real_parallel_map", run)


def test_concurrency_real_channel():
    def run():
        from epl.concurrency_real import Channel, run_in_thread
        ch = Channel(10)

        def producer():
            for i in range(5):
                ch.send(i)
            ch.close()

        t = run_in_thread(producer)
        received = []
        for val in ch:
            received.append(val)

        t.join(5.0)
        assert_eq(received, [0, 1, 2, 3, 4])
    test("concurrency_real_channel", run)


def test_concurrency_real_race():
    def run():
        from epl.concurrency_real import race
        result = race(
            lambda: 'first',
            lambda: 'second'
        )
        assert_in(result, ['first', 'second'])
    test("concurrency_real_race", run)


def test_concurrency_real_all_settled():
    def run():
        from epl.concurrency_real import all_settled
        results = all_settled(
            lambda: 42,
            lambda: 1/0,  # will error
            lambda: 'ok'
        )
        assert_eq(len(results), 3)
        assert_eq(results[0][0], 42)
        assert_true(results[1][1] is not None)  # error
        assert_eq(results[2][0], 'ok')
    test("concurrency_real_all_settled", run)


def test_networking_direct():
    def run():
        from epl.networking import dns_lookup, get_hostname, get_local_ip, is_port_open, UDPSocket
        ip = dns_lookup('localhost')
        assert_in(ip, ['127.0.0.1', '::1'])
        hostname = get_hostname()
        assert_true(len(hostname) > 0)
        local_ip = get_local_ip()
        assert_true('.' in local_ip or ':' in local_ip)
        assert_false(is_port_open('127.0.0.1', 1, 0.3))
        sock = UDPSocket()
        sock.close()
    test("networking_direct", run)


def test_vm_direct():
    def run():
        from epl.vm import compile_and_run, compile_to_bytecode, disassemble
        result = compile_and_run('set x to 42.\nshow x.')
        assert_true('output' in result or 'error' in result)

        bc = compile_to_bytecode('set x to 10.')
        assert_true(bc is not None)

        dis = disassemble('set x to 5.')
        assert_isinstance(dis, str)
    test("vm_direct", run)


def test_packager_imports():
    def run():
        from epl.packager import BuildConfig, DependencyScanner, package
        config = BuildConfig(source_file='test.epl', name='test', version='1.0.0')
        assert_eq(config.output_name, 'test')
    test("packager_imports", run)


# ═══════════════════════════════════════════════════════════
#  Run All
# ═══════════════════════════════════════════════════════════

test_stdlib_has_new_functions.__test__ = False
test_db_connect_close.__test__ = False
test_db_create_table_and_insert.__test__ = False
test_db_query_and_query_one.__test__ = False
test_db_update_and_delete.__test__ = False
test_db_find_by_id.__test__ = False
test_db_table_exists.__test__ = False
test_db_transactions.__test__ = False
test_db_model_crud.__test__ = False
test_mutex_lock_unlock.__test__ = False
test_atomic_int_operations.__test__ = False
test_atomic_bool_operations.__test__ = False
test_channel_send_receive.__test__ = False
test_event_set_wait.__test__ = False
test_semaphore_acquire_release.__test__ = False
test_waitgroup.__test__ = False
test_cpu_count.__test__ = False
test_current_thread.__test__ = False
test_active_threads.__test__ = False
test_sleep_ms.__test__ = False
test_process_run.__test__ = False
test_rwlock.__test__ = False
test_barrier.__test__ = False
test_dns_lookup.__test__ = False
test_hostname.__test__ = False
test_local_ip.__test__ = False
test_is_port_open.__test__ = False
test_udp_socket_create_close.__test__ = False
test_http_client_create.__test__ = False
test_vm_run.__test__ = False
test_vm_compile.__test__ = False
test_vm_disassemble.__test__ = False
test_database_real_direct.__test__ = False
test_database_real_query_builder.__test__ = False
test_database_real_model.__test__ = False
test_concurrency_real_thread.__test__ = False
test_concurrency_real_parallel_map.__test__ = False
test_concurrency_real_channel.__test__ = False
test_concurrency_real_race.__test__ = False
test_concurrency_real_all_settled.__test__ = False
test_networking_direct.__test__ = False
test_vm_direct.__test__ = False
test_packager_imports.__test__ = False

def run_all():
    RESULTS["passed"] = 0
    RESULTS["failed"] = 0
    RESULTS["errors"].clear()
    print("\n" + "=" * 60)
    print("  EPL v3.0 New Modules Test Suite")
    print("=" * 60)

    print("\n── I. STDLIB Integration ──")
    test_stdlib_has_new_functions()

    print("\n── II. Real Database ──")
    test_db_connect_close()
    test_db_create_table_and_insert()
    test_db_query_and_query_one()
    test_db_update_and_delete()
    test_db_find_by_id()
    test_db_table_exists()
    test_db_transactions()
    test_db_model_crud()

    print("\n── III. Concurrency ──")
    test_mutex_lock_unlock()
    test_atomic_int_operations()
    test_atomic_bool_operations()
    test_channel_send_receive()
    test_event_set_wait()
    test_semaphore_acquire_release()
    test_waitgroup()
    test_cpu_count()
    test_current_thread()
    test_active_threads()
    test_sleep_ms()
    test_process_run()
    test_rwlock()
    test_barrier()

    print("\n── IV. Networking ──")
    test_dns_lookup()
    test_hostname()
    test_local_ip()
    test_is_port_open()
    test_udp_socket_create_close()
    test_http_client_create()

    print("\n── V. Bytecode VM ──")
    test_vm_run()
    test_vm_compile()
    test_vm_disassemble()

    print("\n── VI. Direct Module Tests ──")
    test_database_real_direct()
    test_database_real_query_builder()
    test_database_real_model()
    test_concurrency_real_thread()
    test_concurrency_real_parallel_map()
    test_concurrency_real_channel()
    test_concurrency_real_race()
    test_concurrency_real_all_settled()
    test_networking_direct()
    test_vm_direct()
    test_packager_imports()

    print("\n" + "=" * 60)
    total = RESULTS["passed"] + RESULTS["failed"]
    print(f"  Results: {RESULTS['passed']}/{total} passed, {RESULTS['failed']} failed")

    if RESULTS["errors"]:
        print("\n  Failures:")
        for name, err in RESULTS["errors"]:
            print(f"    {name}: {err}")

    if RESULTS["failed"] == 0:
        print("  All tests passed!")
    print("=" * 60)

    return RESULTS["failed"] == 0


def test_new_modules_suite():
    result = subprocess.run(
        [sys.executable, os.path.abspath(__file__)],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == "__main__":
    raise SystemExit(0 if run_all() else 1)
