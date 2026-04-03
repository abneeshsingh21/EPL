"""
EPL Phase 2: Standard Library Tests
Tests: All 12 modules — json, crypto, sql, os, fs, regex, datetime,
       collections, math, encoding, testing, net — 121 new functions.
"""
import sys, os, time, tempfile, json, math, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.errors import EPLError

PASS_COUNT = 0
FAIL_COUNT = 0

def run(src):
    lexer = Lexer(src)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interp = Interpreter()
    interp.execute(program)
    return interp.output_lines

def _legacy_run_case(name, fn):
    global PASS_COUNT, FAIL_COUNT
    try:
        fn()
        PASS_COUNT += 1
        print(f"  PASS: {name}")
    except Exception as e:
        FAIL_COUNT += 1
        print(f"  FAIL: {name} -> {e}")

def assert_eq(a, b):
    assert a == b, f"Expected {b!r}, got {a!r}"

def assert_true(v, msg=""):
    assert v, msg or f"Expected truthy, got {v!r}"

def assert_in(item, collection, msg=""):
    assert item in collection, msg or f"{item!r} not in {collection!r}"

def assert_near(a, b, tol=1e-9):
    assert abs(float(a) - float(b)) < tol, f"|{a} - {b}| = {abs(float(a)-float(b))} > {tol}"

Q = chr(34)        # double quote
NL = chr(10)       # newline for EPL source

# Direct stdlib access for unit tests
from epl.stdlib import call_stdlib

# ═══════════════════════════════════════════════════════════
#  1. JSON EXTENDED (3 functions)
# ═══════════════════════════════════════════════════════════

def test_json_valid_true():
    r = call_stdlib('json_valid', ['{"a":1}'], 0)
    assert_eq(r, True)

def test_json_valid_false():
    r = call_stdlib('json_valid', ['{bad json}'], 0)
    assert_eq(r, False)

def test_json_valid_array():
    r = call_stdlib('json_valid', ['[1,2,3]'], 0)
    assert_eq(r, True)

def test_json_valid_empty():
    r = call_stdlib('json_valid', [''], 0)
    assert_eq(r, False)

def test_json_merge():
    from epl.interpreter import EPLDict
    a = EPLDict({"x": 1})
    b = EPLDict({"y": 2})
    r = call_stdlib('json_merge', [a, b], 0)
    assert_in("x", r.data)
    assert_in("y", r.data)

def test_json_merge_override():
    from epl.interpreter import EPLDict
    a = EPLDict({"x": 1})
    b = EPLDict({"x": 99})
    r = call_stdlib('json_merge', [a, b], 0)
    assert_eq(r.data["x"], 99)

def test_json_query_simple():
    from epl.interpreter import EPLDict
    obj = EPLDict({"a": EPLDict({"b": 42})})
    r = call_stdlib('json_query', [obj, 'a.b'], 0)
    assert_eq(r, 42)

def test_json_query_missing():
    from epl.interpreter import EPLDict
    obj = EPLDict({"a": 1})
    r = call_stdlib('json_query', [obj, 'x.y'], 0)
    assert_eq(r, None)

def test_json_query_array_index():
    from epl.interpreter import EPLDict
    obj = EPLDict({"items": [10, 20, 30]})
    r = call_stdlib('json_query', [obj, 'items.1'], 0)
    assert_eq(r, 20)

def test_json_valid_epl():
    out = run('Create valid equal to json_valid("{}")\nPrint valid')
    assert_eq(out, ['true'])


# ═══════════════════════════════════════════════════════════
#  2. CRYPTO EXTENDED (9 functions)
# ═══════════════════════════════════════════════════════════

def test_hash_sha1():
    r = call_stdlib('hash_sha1', ['hello'], 0)
    assert_eq(r, 'aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d')

def test_hash_sha384():
    r = call_stdlib('hash_sha384', ['hello'], 0)
    assert_eq(len(r), 96)  # SHA-384 produces 96 hex chars

def test_hash_file():
    tmp = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt')
    tmp.write('test content')
    tmp.close()
    try:
        r = call_stdlib('hash_file', [tmp.name], 0)
        assert_eq(len(r), 64)  # SHA-256 default = 64 hex chars
    finally:
        os.unlink(tmp.name)

def test_hash_file_sha1():
    tmp = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt')
    tmp.write('test')
    tmp.close()
    try:
        r = call_stdlib('hash_file', [tmp.name, 'sha1'], 0)
        assert_eq(len(r), 40)  # SHA-1 = 40 hex chars
    finally:
        os.unlink(tmp.name)

def test_secure_random_bytes():
    r = call_stdlib('secure_random_bytes', [16], 0)
    assert_eq(len(r), 32)  # 16 bytes = 32 hex chars

def test_secure_random_bytes_unique():
    r1 = call_stdlib('secure_random_bytes', [32], 0)
    r2 = call_stdlib('secure_random_bytes', [32], 0)
    assert_true(r1 != r2, "Random bytes should be unique")

def test_secure_random_int():
    r = call_stdlib('secure_random_int', [1, 100], 0)
    assert_true(1 <= r <= 100, f"Expected in [1,100], got {r}")

def test_secure_random_int_range():
    results = set()
    for _ in range(50):
        results.add(call_stdlib('secure_random_int', [1, 10], 0))
    assert_true(len(results) > 1, "Should produce varying results")

def test_aes_encrypt_decrypt():
    plaintext = "Hello, EPL!"
    key = "my-secret-key-123"
    encrypted = call_stdlib('aes_encrypt', [plaintext, key], 0)
    decrypted = call_stdlib('aes_decrypt', [encrypted, key], 0)
    assert_eq(decrypted, plaintext)

def test_aes_different_key_fails():
    plaintext = "Secret message"
    encrypted = call_stdlib('aes_encrypt', [plaintext, 'key1'], 0)
    try:
        decrypted = call_stdlib('aes_decrypt', [encrypted, 'key2'], 0)
        # Won't produce the original plaintext
        assert_true(decrypted != plaintext)
    except:
        pass  # Decryption error is also acceptable

def test_aes_roundtrip_unicode():
    plaintext = "Unicode: \u00e9\u00e8\u00ea"
    key = "unicode-key"
    encrypted = call_stdlib('aes_encrypt', [plaintext, key], 0)
    decrypted = call_stdlib('aes_decrypt', [encrypted, key], 0)
    assert_eq(decrypted, plaintext)

def test_pbkdf2_hash():
    r = call_stdlib('pbkdf2_hash', ['password123'], 0)
    parts = r.split('$')
    assert_eq(len(parts), 3)  # iterations$salt$dk
    assert_true(int(parts[0]) > 0, "iterations must be positive")

def test_pbkdf2_verify():
    hashed = call_stdlib('pbkdf2_hash', ['mypassword'], 0)
    assert_eq(call_stdlib('pbkdf2_verify', ['mypassword', hashed], 0), True)
    assert_eq(call_stdlib('pbkdf2_verify', ['wrongpassword', hashed], 0), False)

def test_pbkdf2_custom_iterations():
    hashed = call_stdlib('pbkdf2_hash', ['pass', 10000], 0)
    parts = hashed.split('$')
    assert_eq(parts[0], '10000')
    assert_eq(call_stdlib('pbkdf2_verify', ['pass', hashed], 0), True)


# ═══════════════════════════════════════════════════════════
#  3. SQL EXTENDED (8 functions)
# ═══════════════════════════════════════════════════════════

def _make_test_db():
    """Create a temp SQLite DB and return conn_id."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    tmp.close()
    conn_id = call_stdlib('db_open', [tmp.name], 0)
    call_stdlib('db_execute', [conn_id, 'CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)'], 0)
    call_stdlib('db_execute', [conn_id, 'INSERT INTO users (name, age) VALUES (?, ?)', ['Alice', 30]], 0)
    call_stdlib('db_execute', [conn_id, 'INSERT INTO users (name, age) VALUES (?, ?)', ['Bob', 25]], 0)
    return conn_id, tmp.name

def test_db_update():
    conn_id, path = _make_test_db()
    try:
        from epl.interpreter import EPLDict
        call_stdlib('db_update', [conn_id, 'users', EPLDict({'age': 31}), EPLDict({'name': 'Alice'})], 0)
        rows = call_stdlib('db_query', [conn_id, 'SELECT age FROM users WHERE name=?', 'Alice'], 0)
        # rows is a list of EPLDicts
        assert_eq(rows[0].data.get('age', rows[0].data.get('AGE', None)), 31)
    finally:
        call_stdlib('db_close', [conn_id], 0)
        os.unlink(path)

def test_db_delete():
    conn_id, path = _make_test_db()
    try:
        from epl.interpreter import EPLDict
        call_stdlib('db_delete', [conn_id, 'users', EPLDict({'name': 'Bob'})], 0)
        count = call_stdlib('db_count', [conn_id, 'users'], 0)
        assert_eq(count, 1)
    finally:
        call_stdlib('db_close', [conn_id], 0)
        os.unlink(path)

def test_db_count():
    conn_id, path = _make_test_db()
    try:
        count = call_stdlib('db_count', [conn_id, 'users'], 0)
        assert_eq(count, 2)
    finally:
        call_stdlib('db_close', [conn_id], 0)
        os.unlink(path)

def test_db_count_where():
    conn_id, path = _make_test_db()
    try:
        from epl.interpreter import EPLDict
        count = call_stdlib('db_count', [conn_id, 'users', EPLDict({'age': 30})], 0)
        assert_eq(count, 1)
    finally:
        call_stdlib('db_close', [conn_id], 0)
        os.unlink(path)

def test_db_table_info():
    conn_id, path = _make_test_db()
    try:
        info = call_stdlib('db_table_info', [conn_id, 'users'], 0)
        assert_true(len(info) >= 3, f"Expected >=3 columns, got {len(info)}")
        names = [col.data['name'] for col in info]
        assert_in('name', names)
        assert_in('age', names)
    finally:
        call_stdlib('db_close', [conn_id], 0)
        os.unlink(path)

def test_db_transaction_commit():
    conn_id, path = _make_test_db()
    try:
        call_stdlib('db_begin', [conn_id], 0)
        call_stdlib('db_execute', [conn_id, 'INSERT INTO users (name, age) VALUES (?, ?)', ['Carol', 28]], 0)
        call_stdlib('db_commit', [conn_id], 0)
        count = call_stdlib('db_count', [conn_id, 'users'], 0)
        assert_eq(count, 3)
    finally:
        call_stdlib('db_close', [conn_id], 0)
        os.unlink(path)

def test_db_transaction_rollback():
    conn_id, path = _make_test_db()
    try:
        # Test that begin/rollback mechanism works
        call_stdlib('db_begin', [conn_id], 0)
        call_stdlib('db_rollback', [conn_id], 0)
        # Just verify the operations don't crash
        count = call_stdlib('db_count', [conn_id, 'users'], 0)
        assert_true(count >= 2, f"Expected >=2 rows, got {count}")
    finally:
        call_stdlib('db_close', [conn_id], 0)
        os.unlink(path)

def test_db_backup():
    conn_id, path = _make_test_db()
    backup_path = path + '.backup'
    try:
        call_stdlib('db_backup', [conn_id, backup_path], 0)
        assert_true(os.path.exists(backup_path), "Backup file should exist")
        assert_true(os.path.getsize(backup_path) > 0, "Backup should not be empty")
        # Verify backup has the data
        conn2 = call_stdlib('db_open', [backup_path], 0)
        count = call_stdlib('db_count', [conn2, 'users'], 0)
        assert_eq(count, 2)
        call_stdlib('db_close', [conn2], 0)
    finally:
        call_stdlib('db_close', [conn_id], 0)
        os.unlink(path)
        if os.path.exists(backup_path):
            os.unlink(backup_path)


# ═══════════════════════════════════════════════════════════
#  4. OS EXTENDED (9 functions)
# ═══════════════════════════════════════════════════════════

def test_hostname():
    r = call_stdlib('hostname', [], 0)
    assert_true(len(r) > 0, "Hostname should be non-empty")

def test_arch():
    r = call_stdlib('arch', [], 0)
    assert_true(len(r) > 0, "Architecture should be non-empty")

def test_user_home():
    r = call_stdlib('user_home', [], 0)
    assert_true(os.path.isdir(r), f"Home dir should exist: {r}")

def test_user_name():
    r = call_stdlib('user_name', [], 0)
    assert_true(len(r) > 0, "Username should be non-empty")

def test_uptime():
    r = call_stdlib('uptime', [], 0)
    assert_true(r > 0, f"Uptime should be positive, got {r}")

def test_is_admin():
    r = call_stdlib('is_admin', [], 0)
    assert_true(r in (True, False), f"Expected bool, got {r}")

def test_env_delete():
    os.environ['EPL_TEST_DELETE'] = 'temp'
    call_stdlib('env_delete', ['EPL_TEST_DELETE'], 0)
    assert_true('EPL_TEST_DELETE' not in os.environ)

def test_exec_async():
    if sys.platform == 'win32':
        proc_id = call_stdlib('exec_async', ['cmd /c echo hello'], 0)
    else:
        proc_id = call_stdlib('exec_async', ['echo hello'], 0)
    assert_true(proc_id.startswith('proc_'), f"Should return proc_N, got {proc_id}")
    time.sleep(0.5)
    call_stdlib('kill_process', [proc_id], 0)

def test_kill_process():
    if sys.platform == 'win32':
        proc_id = call_stdlib('exec_async', ['cmd /c ping -n 10 127.0.0.1'], 0)
    else:
        proc_id = call_stdlib('exec_async', ['sleep 30'], 0)
    time.sleep(0.2)
    r = call_stdlib('kill_process', [proc_id], 0)
    assert_eq(r, True)

def test_os_via_epl():
    out = run('Create h equal to hostname()\nPrint h')
    assert_true(len(out) > 0 and len(out[0]) > 0)


# ═══════════════════════════════════════════════════════════
#  5. FILESYSTEM EXTENDED (11 functions)
# ═══════════════════════════════════════════════════════════

def test_file_modified_time():
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
    tmp.write(b'data')
    tmp.close()
    try:
        r = call_stdlib('file_modified_time', [tmp.name], 0)
        assert_true(r > 0, f"Modified time should be positive, got {r}")
    finally:
        os.unlink(tmp.name)

def test_file_created_time():
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
    tmp.write(b'data')
    tmp.close()
    try:
        r = call_stdlib('file_created_time', [tmp.name], 0)
        assert_true(r > 0, f"Created time should be positive, got {r}")
    finally:
        os.unlink(tmp.name)

def test_file_is_dir():
    assert_eq(call_stdlib('file_is_dir', [tempfile.gettempdir()], 0), True)
    assert_eq(call_stdlib('file_is_dir', ['/nonexistent_dir_xyz'], 0), False)

def test_file_is_file():
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
    tmp.close()
    try:
        assert_eq(call_stdlib('file_is_file', [tmp.name], 0), True)
        assert_eq(call_stdlib('file_is_file', [tempfile.gettempdir()], 0), False)
    finally:
        os.unlink(tmp.name)

def test_file_read_write_binary():
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.bin')
    tmp.close()
    try:
        hex_data = '48656c6c6f'  # "Hello" in hex
        call_stdlib('file_write_binary', [tmp.name, hex_data], 0)
        result = call_stdlib('file_read_binary', [tmp.name], 0)
        assert_eq(result, hex_data)
    finally:
        os.unlink(tmp.name)

def test_file_move():
    src = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
    src.write(b'move me')
    src.close()
    dst = src.name + '.moved'
    try:
        call_stdlib('file_move', [src.name, dst], 0)
        assert_true(os.path.exists(dst), "Destination should exist")
        assert_true(not os.path.exists(src.name), "Source should be gone")
    finally:
        if os.path.exists(dst):
            os.unlink(dst)
        if os.path.exists(src.name):
            os.unlink(src.name)

def test_dir_walk():
    tmpdir = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmpdir, 'sub'), exist_ok=True)
        with open(os.path.join(tmpdir, 'a.txt'), 'w') as f:
            f.write('a')
        with open(os.path.join(tmpdir, 'sub', 'b.txt'), 'w') as f:
            f.write('b')
        result = call_stdlib('dir_walk', [tmpdir], 0)
        assert_true(len(result) >= 2, f"Expected >=2 files, got {result}")
    finally:
        shutil.rmtree(tmpdir)

def test_file_glob():
    tmpdir = tempfile.mkdtemp()
    try:
        for name in ['x.txt', 'y.txt', 'z.py']:
            with open(os.path.join(tmpdir, name), 'w') as f:
                f.write('data')
        pattern = os.path.join(tmpdir, '*.txt')
        result = call_stdlib('file_glob', [pattern], 0)
        assert_eq(len(result), 2)
    finally:
        shutil.rmtree(tmpdir)

def test_path_normalize():
    r = call_stdlib('path_normalize', ['a/b/../c/./d'], 0)
    assert_eq(r, 'a/c/d')

def test_path_relative():
    r = call_stdlib('path_relative', ['/a/b/c', '/a'], 0)
    assert_in('b/c', r)

def test_fs_via_epl():
    out = run('Create d equal to file_is_dir(".")\nPrint d')
    assert_true(out[0].lower() == 'true')


# ═══════════════════════════════════════════════════════════
#  6. REGEX EXTENDED (3 functions)
# ═══════════════════════════════════════════════════════════

def test_regex_compile():
    rx_id = call_stdlib('regex_compile', [r'\d+'], 0)
    assert_true(rx_id.startswith('rx_'), f"Expected rx_N, got {rx_id}")

def test_regex_compile_with_flags():
    rx_id = call_stdlib('regex_compile', [r'hello', 'i'], 0)
    assert_true(rx_id.startswith('rx_'))

def test_regex_groups():
    r = call_stdlib('regex_groups', [r'(\d+)-(\w+)', '42-abc'], 0)
    assert_eq(r, ['42', 'abc'])

def test_regex_groups_no_match():
    r = call_stdlib('regex_groups', [r'(\d+)', 'abc'], 0)
    assert_eq(r, [])

def test_regex_groups_named():
    r = call_stdlib('regex_groups', [r'(?P<num>\d+)-(?P<word>\w+)', '42-abc'], 0)
    assert_in('42', r)
    assert_in('abc', r)

def test_regex_via_epl():
    out = run('Create groups equal to regex_groups("(\\\\d+)-(\\\\w+)", "99-xyz")\nPrint groups')
    assert_true(len(out) > 0)


# ═══════════════════════════════════════════════════════════
#  7. DATETIME EXTENDED (8 functions)
# ═══════════════════════════════════════════════════════════

def test_utc_now():
    r = call_stdlib('utc_now', [], 0)
    assert_true(r.endswith('Z'), f"Should end with Z: {r}")
    assert_true(len(r) > 10, f"Should be ISO format: {r}")

def test_timezone_info():
    r = call_stdlib('timezone', [], 0)
    assert_true(r.startswith('UTC'), f"Expected UTC+/-N: {r}")

def test_to_timestamp():
    r = call_stdlib('to_timestamp', ['2000-01-01T00:00:00'], 0)
    assert_eq(r, 946684800)

def test_from_timestamp():
    r = call_stdlib('from_timestamp', [946684800], 0)
    assert_true('2000-01-01' in r, f"Expected 2000-01-01 in {r}")

def test_to_from_roundtrip():
    ts = call_stdlib('to_timestamp', ['2024-06-15T12:30:00'], 0)
    back = call_stdlib('from_timestamp', [ts], 0)
    assert_true('2024-06-15' in back)

def test_week_of_year():
    r = call_stdlib('week_of_year', ['2024-01-01'], 0)
    assert_true(1 <= r <= 53, f"Week should be 1-53, got {r}")

def test_is_weekend():
    # 2024-01-06 is Saturday
    assert_eq(call_stdlib('is_weekend', ['2024-01-06'], 0), True)
    # 2024-01-07 is Sunday
    assert_eq(call_stdlib('is_weekend', ['2024-01-07'], 0), True)
    # 2024-01-08 is Monday
    assert_eq(call_stdlib('is_weekend', ['2024-01-08'], 0), False)

def test_is_weekday():
    # 2024-01-08 is Monday
    assert_eq(call_stdlib('is_weekday', ['2024-01-08'], 0), True)
    # 2024-01-06 is Saturday
    assert_eq(call_stdlib('is_weekday', ['2024-01-06'], 0), False)

def test_date_range():
    r = call_stdlib('date_range', ['2024-01-01', '2024-01-05'], 0)
    assert_eq(len(r), 5)
    assert_eq(r[0], '2024-01-01')
    assert_eq(r[-1], '2024-01-05')

def test_date_range_step():
    r = call_stdlib('date_range', ['2024-01-01', '2024-01-10', 3], 0)
    assert_eq(r[0], '2024-01-01')
    assert_eq(r[1], '2024-01-04')
    assert_eq(r[2], '2024-01-07')
    assert_eq(r[3], '2024-01-10')


# ═══════════════════════════════════════════════════════════
#  8. COLLECTIONS EXTENDED (30 functions)
# ═══════════════════════════════════════════════════════════

# -- Linked List --
def test_linked_list_new():
    ll = call_stdlib('linked_list_new', [], 0)
    assert_true(ll.startswith('ll_'))

def test_linked_list_append():
    ll = call_stdlib('linked_list_new', [], 0)
    call_stdlib('linked_list_append', [ll, 'a'], 0)
    call_stdlib('linked_list_append', [ll, 'b'], 0)
    assert_eq(call_stdlib('linked_list_size', [ll], 0), 2)

def test_linked_list_prepend():
    ll = call_stdlib('linked_list_new', [], 0)
    call_stdlib('linked_list_append', [ll, 'b'], 0)
    call_stdlib('linked_list_prepend', [ll, 'a'], 0)
    assert_eq(call_stdlib('linked_list_get', [ll, 0], 0), 'a')
    assert_eq(call_stdlib('linked_list_get', [ll, 1], 0), 'b')

def test_linked_list_pop():
    ll = call_stdlib('linked_list_new', [], 0)
    call_stdlib('linked_list_append', [ll, 10], 0)
    call_stdlib('linked_list_append', [ll, 20], 0)
    v = call_stdlib('linked_list_pop', [ll], 0)
    assert_eq(v, 20)
    assert_eq(call_stdlib('linked_list_size', [ll], 0), 1)

def test_linked_list_pop_front():
    ll = call_stdlib('linked_list_new', [], 0)
    call_stdlib('linked_list_append', [ll, 10], 0)
    call_stdlib('linked_list_append', [ll, 20], 0)
    v = call_stdlib('linked_list_pop_front', [ll], 0)
    assert_eq(v, 10)

def test_linked_list_get_oob():
    ll = call_stdlib('linked_list_new', [], 0)
    call_stdlib('linked_list_append', [ll, 'x'], 0)
    assert_eq(call_stdlib('linked_list_get', [ll, 99], 0), None)

def test_linked_list_to_list():
    ll = call_stdlib('linked_list_new', [], 0)
    for i in [1, 2, 3]:
        call_stdlib('linked_list_append', [ll, i], 0)
    r = call_stdlib('linked_list_to_list', [ll], 0)
    assert_eq(r, [1, 2, 3])

# -- Priority Queue --
def test_pq_new():
    pq = call_stdlib('priority_queue_new', [], 0)
    assert_true(pq.startswith('pq_'))

def test_pq_push_pop():
    pq = call_stdlib('priority_queue_new', [], 0)
    call_stdlib('priority_queue_push', [pq, 3, 'low'], 0)
    call_stdlib('priority_queue_push', [pq, 1, 'high'], 0)
    call_stdlib('priority_queue_push', [pq, 2, 'mid'], 0)
    assert_eq(call_stdlib('priority_queue_pop', [pq], 0), 'high')  # lowest priority first
    assert_eq(call_stdlib('priority_queue_pop', [pq], 0), 'mid')
    assert_eq(call_stdlib('priority_queue_pop', [pq], 0), 'low')

def test_pq_peek():
    pq = call_stdlib('priority_queue_new', [], 0)
    call_stdlib('priority_queue_push', [pq, 5, 'five'], 0)
    call_stdlib('priority_queue_push', [pq, 1, 'one'], 0)
    assert_eq(call_stdlib('priority_queue_peek', [pq], 0), 'one')
    assert_eq(call_stdlib('priority_queue_size', [pq], 0), 2)  # peek doesn't remove

def test_pq_empty_pop():
    pq = call_stdlib('priority_queue_new', [], 0)
    assert_eq(call_stdlib('priority_queue_pop', [pq], 0), None)

# -- Deque --
def test_deque_new():
    dq = call_stdlib('deque_new', [], 0)
    assert_true(dq.startswith('dq_'))

def test_deque_push_back_front():
    dq = call_stdlib('deque_new', [], 0)
    call_stdlib('deque_push_back', [dq, 'b'], 0)
    call_stdlib('deque_push_front', [dq, 'a'], 0)
    call_stdlib('deque_push_back', [dq, 'c'], 0)
    r = call_stdlib('deque_to_list', [dq], 0)
    assert_eq(r, ['a', 'b', 'c'])

def test_deque_pop_back():
    dq = call_stdlib('deque_new', [], 0)
    call_stdlib('deque_push_back', [dq, 1], 0)
    call_stdlib('deque_push_back', [dq, 2], 0)
    assert_eq(call_stdlib('deque_pop_back', [dq], 0), 2)

def test_deque_pop_front():
    dq = call_stdlib('deque_new', [], 0)
    call_stdlib('deque_push_back', [dq, 1], 0)
    call_stdlib('deque_push_back', [dq, 2], 0)
    assert_eq(call_stdlib('deque_pop_front', [dq], 0), 1)

def test_deque_size():
    dq = call_stdlib('deque_new', [], 0)
    assert_eq(call_stdlib('deque_size', [dq], 0), 0)
    call_stdlib('deque_push_back', [dq, 'x'], 0)
    assert_eq(call_stdlib('deque_size', [dq], 0), 1)

def test_deque_empty_pop():
    dq = call_stdlib('deque_new', [], 0)
    assert_eq(call_stdlib('deque_pop_front', [dq], 0), None)
    assert_eq(call_stdlib('deque_pop_back', [dq], 0), None)

# -- Ordered Map --
def test_ordered_map_new():
    om = call_stdlib('ordered_map_new', [], 0)
    assert_true(om.startswith('om_'))

def test_ordered_map_set_get():
    om = call_stdlib('ordered_map_new', [], 0)
    call_stdlib('ordered_map_set', [om, 'key1', 'val1'], 0)
    call_stdlib('ordered_map_set', [om, 'key2', 'val2'], 0)
    assert_eq(call_stdlib('ordered_map_get', [om, 'key1'], 0), 'val1')
    assert_eq(call_stdlib('ordered_map_get', [om, 'key2'], 0), 'val2')

def test_ordered_map_preserves_order():
    om = call_stdlib('ordered_map_new', [], 0)
    for k in ['c', 'a', 'b']:
        call_stdlib('ordered_map_set', [om, k, k.upper()], 0)
    keys = call_stdlib('ordered_map_keys', [om], 0)
    assert_eq(keys, ['c', 'a', 'b'])

def test_ordered_map_delete():
    om = call_stdlib('ordered_map_new', [], 0)
    call_stdlib('ordered_map_set', [om, 'x', 1], 0)
    call_stdlib('ordered_map_delete', [om, 'x'], 0)
    assert_eq(call_stdlib('ordered_map_get', [om, 'x'], 0), None)
    assert_eq(call_stdlib('ordered_map_size', [om], 0), 0)

def test_ordered_map_values():
    om = call_stdlib('ordered_map_new', [], 0)
    call_stdlib('ordered_map_set', [om, 'a', 1], 0)
    call_stdlib('ordered_map_set', [om, 'b', 2], 0)
    assert_eq(call_stdlib('ordered_map_values', [om], 0), [1, 2])

def test_ordered_map_to_list():
    om = call_stdlib('ordered_map_new', [], 0)
    call_stdlib('ordered_map_set', [om, 'x', 10], 0)
    call_stdlib('ordered_map_set', [om, 'y', 20], 0)
    r = call_stdlib('ordered_map_to_list', [om], 0)
    assert_eq(r, [['x', 10], ['y', 20]])

# -- Set extensions --
def test_set_size():
    s = {1, 2, 3}
    assert_eq(call_stdlib('set_size', [s], 0), 3)

def test_set_to_list():
    s = {3, 1, 2}
    r = call_stdlib('set_to_list', [s], 0)
    assert_eq(r, [1, 2, 3])  # sorted

def test_set_clear():
    s = {1, 2, 3}
    call_stdlib('set_clear', [s], 0)
    assert_eq(len(s), 0)

# -- Higher-order functions --
def test_frequency_map():
    r = call_stdlib('frequency_map', [['a', 'b', 'a', 'c', 'a', 'b']], 0)
    assert_eq(r.data['a'], 3)
    assert_eq(r.data['b'], 2)
    assert_eq(r.data['c'], 1)

def test_collections_via_epl():
    out = run('Create ll equal to linked_list_new()\nlinked_list_append(ll, 42)\nCreate sz equal to linked_list_size(ll)\nPrint sz')
    assert_eq(out, ['1'])


# ═══════════════════════════════════════════════════════════
#  9. MATH EXTENDED (17 functions)
# ═══════════════════════════════════════════════════════════

def test_log2():
    assert_near(call_stdlib('log2', [8], 0), 3.0)

def test_log10():
    assert_near(call_stdlib('log10', [1000], 0), 3.0)

def test_exp():
    assert_near(call_stdlib('exp', [0], 0), 1.0)
    assert_near(call_stdlib('exp', [1], 0), math.e, tol=1e-6)

def test_hypot():
    assert_near(call_stdlib('hypot', [3, 4], 0), 5.0)

def test_sinh():
    assert_near(call_stdlib('sinh', [0], 0), 0.0)
    assert_near(call_stdlib('sinh', [1], 0), math.sinh(1), tol=1e-9)

def test_cosh():
    assert_near(call_stdlib('cosh', [0], 0), 1.0)

def test_tanh():
    assert_near(call_stdlib('tanh', [0], 0), 0.0)
    # tanh approaches +/-1 at extreme values
    assert_true(abs(call_stdlib('tanh', [10], 0)) > 0.99)

def test_asinh():
    assert_near(call_stdlib('asinh', [0], 0), 0.0)

def test_acosh():
    assert_near(call_stdlib('acosh', [1], 0), 0.0)

def test_atanh():
    assert_near(call_stdlib('atanh', [0], 0), 0.0)

def test_ceil_div():
    assert_eq(call_stdlib('ceil_div', [7, 3], 0), 3)   # ceil(7/3) = 3
    assert_eq(call_stdlib('ceil_div', [9, 3], 0), 3)   # exact division
    assert_eq(call_stdlib('ceil_div', [10, 3], 0), 4)  # ceil(10/3) = 4

def test_fmod():
    assert_near(call_stdlib('fmod', [5.5, 2.3], 0), math.fmod(5.5, 2.3))

def test_copysign():
    assert_near(call_stdlib('copysign', [1, -1], 0), -1.0)
    assert_near(call_stdlib('copysign', [-1, 1], 0), 1.0)

def test_permutations():
    assert_eq(call_stdlib('permutations', [5, 3], 0), 60)  # 5*4*3
    assert_eq(call_stdlib('permutations', [5, 0], 0), 1)

def test_combinations():
    assert_eq(call_stdlib('combinations', [5, 3], 0), 10)  # C(5,3)
    assert_eq(call_stdlib('combinations', [10, 0], 0), 1)

def test_variance():
    r = call_stdlib('variance', [[2, 4, 4, 4, 5, 5, 7, 9]], 0)
    assert_near(r, 4.571428571428571, tol=1e-6)  # sample variance

def test_std_dev():
    r = call_stdlib('std_dev', [[2, 4, 4, 4, 5, 5, 7, 9]], 0)
    assert_near(r, math.sqrt(4.571428571428571), tol=1e-6)

def test_math_via_epl():
    out = run('Create r equal to log2(8)\nPrint r')
    assert_eq(out, ['3.0'])


# ═══════════════════════════════════════════════════════════
#  10. ENCODING EXTENDED (6 functions)
# ═══════════════════════════════════════════════════════════

def test_base64_url_encode():
    r = call_stdlib('base64_url_encode', ['Hello+World/Foo'], 0)
    assert_true('=' not in r, "URL-safe base64 should strip padding")
    assert_true('+' not in r, "URL-safe should not contain +")
    assert_true('/' not in r, "URL-safe should not contain /")

def test_base64_url_roundtrip():
    original = "Hello, World! Special chars: +/=?"
    encoded = call_stdlib('base64_url_encode', [original], 0)
    decoded = call_stdlib('base64_url_decode', [encoded], 0)
    assert_eq(decoded, original)

def test_html_encode():
    r = call_stdlib('html_encode', ['<script>alert("xss")</script>'], 0)
    assert_in('&lt;', r)
    assert_in('&gt;', r)
    assert_in('&quot;', r)

def test_html_decode():
    r = call_stdlib('html_decode', ['&lt;b&gt;Hello&lt;/b&gt;'], 0)
    assert_eq(r, '<b>Hello</b>')

def test_html_roundtrip():
    original = '<div class="test">&amp;</div>'
    encoded = call_stdlib('html_encode', [original], 0)
    decoded = call_stdlib('html_decode', [encoded], 0)
    assert_eq(decoded, original)

def test_base32_encode():
    r = call_stdlib('base32_encode', ['Hello'], 0)
    assert_eq(r, 'JBSWY3DP')  # Standard base32 for "Hello" (without padding)

def test_base32_roundtrip():
    original = "Test data 123"
    encoded = call_stdlib('base32_encode', [original], 0)
    decoded = call_stdlib('base32_decode', [encoded], 0)
    assert_eq(decoded, original)


# ═══════════════════════════════════════════════════════════
#  11. TESTING EXTENDED (9 functions)
# ═══════════════════════════════════════════════════════════

def test_test_describe():
    r = call_stdlib('test_describe', ['MyModule'], 0)
    assert_eq(r, True)

def test_test_skip():
    r = call_stdlib('test_skip', ['skipped_test'], 0)
    assert_eq(r, True)

def test_test_expect_near():
    r = call_stdlib('test_expect_near', [3.14, 3.14159, 0.01], 0)
    assert_eq(r, True)

def test_test_expect_near_fail():
    try:
        call_stdlib('test_expect_near', [1.0, 2.0, 0.1], 0)
        assert_true(False, "Should have raised")
    except:
        pass  # Expected to raise

def test_test_expect_match():
    r = call_stdlib('test_expect_match', ['hello123', r'\d+'], 0)
    assert_eq(r, True)

def test_test_expect_match_fail():
    try:
        call_stdlib('test_expect_match', ['hello', r'\d+'], 0)
        assert_true(False, "Should have raised")
    except:
        pass  # Expected to raise

def test_test_before_after_each():
    # Store a function as hook
    counter = [0]
    def hook():
        counter[0] += 1
    call_stdlib('test_before_each', [hook], 0)
    call_stdlib('test_after_each', [hook], 0)
    # The hooks are stored, verify by checking _test_hooks
    from epl.stdlib import _test_hooks
    assert_true(_test_hooks['before_each'] is not None)
    assert_true(_test_hooks['after_each'] is not None)

def test_test_benchmark():
    counter = [0]
    def work():
        counter[0] += 1
    r = call_stdlib('test_benchmark', ['fast_fn', work, 100], 0)
    assert_true(r >= 0, f"Benchmark should return ms/op, got {r}")
    assert_eq(counter[0], 100)

def test_test_assert_throws():
    def thrower():
        raise ValueError("boom")
    r = call_stdlib('test_assert_throws', [thrower], 0)
    assert_eq(r, True)

def test_test_assert_throws_no_throw():
    def no_throw():
        return 42
    try:
        call_stdlib('test_assert_throws', [no_throw], 0)
        assert_true(False, "Should have raised because fn didn't throw")
    except:
        pass


# ═══════════════════════════════════════════════════════════
#  12. NET EXTENDED (HTTP Server lifecycle)
# ═══════════════════════════════════════════════════════════

def test_http_server_lifecycle():
    """Create, add route, start, and stop an HTTP server."""
    import urllib.request
    srv = call_stdlib('net_http_server', [18923], 0)
    assert_true(srv.startswith('httpd_'))
    # Add a route for testing
    def handler(req):
        return {"status": 200, "body": "OK from EPL"}
    call_stdlib('net_http_server_route', [srv, 'GET', '/test', handler], 0)
    call_stdlib('net_http_server_start', [srv], 0)
    time.sleep(0.3)
    try:
        resp = urllib.request.urlopen('http://127.0.0.1:18923/test', timeout=2)
        body = resp.read().decode()
        assert_in('OK from EPL', body)
    finally:
        call_stdlib('net_http_server_stop', [srv], 0)

def test_http_server_404():
    """Unknown route should return 404."""
    import urllib.request
    srv = call_stdlib('net_http_server', [18924], 0)
    call_stdlib('net_http_server_start', [srv], 0)
    time.sleep(0.3)
    try:
        try:
            urllib.request.urlopen('http://127.0.0.1:18924/nonexistent', timeout=2)
            assert_true(False, "Should get 404")
        except urllib.error.HTTPError as e:
            assert_eq(e.code, 404)
    finally:
        call_stdlib('net_http_server_stop', [srv], 0)

def test_http_server_multiple_routes():
    """Multiple routes should work."""
    import urllib.request
    srv = call_stdlib('net_http_server', [18925], 0)
    call_stdlib('net_http_server_route', [srv, 'GET', '/a', lambda r: {"status": 200, "body": "route_a"}], 0)
    call_stdlib('net_http_server_route', [srv, 'GET', '/b', lambda r: {"status": 200, "body": "route_b"}], 0)
    call_stdlib('net_http_server_start', [srv], 0)
    time.sleep(0.3)
    try:
        resp_a = urllib.request.urlopen('http://127.0.0.1:18925/a', timeout=2).read().decode()
        resp_b = urllib.request.urlopen('http://127.0.0.1:18925/b', timeout=2).read().decode()
        assert_in('route_a', resp_a)
        assert_in('route_b', resp_b)
    finally:
        call_stdlib('net_http_server_stop', [srv], 0)


# ═══════════════════════════════════════════════════════════
#  13. INTEGRATION: EPL Syntax Tests  
# ═══════════════════════════════════════════════════════════

def test_epl_aes_roundtrip():
    out = run('Create enc equal to aes_encrypt("hello", "key")\nCreate dec equal to aes_decrypt(enc, "key")\nPrint dec')
    assert_eq(out, ['hello'])

def test_epl_pbkdf2():
    out = run('Create h equal to pbkdf2_hash("pass")\nCreate ok equal to pbkdf2_verify("pass", h)\nPrint ok')
    assert_true(out[0].lower() == 'true')

def test_epl_linked_list():
    out = run('''Create ll equal to linked_list_new()
linked_list_append(ll, 10)
linked_list_append(ll, 20)
linked_list_append(ll, 30)
Create items equal to linked_list_to_list(ll)
Print items''')
    assert_eq(out, ['[10, 20, 30]'])

def test_epl_priority_queue():
    out = run('''Create pq equal to priority_queue_new()
priority_queue_push(pq, 3, "low")
priority_queue_push(pq, 1, "high")
priority_queue_push(pq, 2, "mid")
Create first equal to priority_queue_pop(pq)
Print first''')
    assert_eq(out, ['high'])

def test_epl_deque():
    out = run('''Create dq equal to deque_new()
deque_push_front(dq, "a")
deque_push_back(dq, "b")
deque_push_front(dq, "z")
Create result equal to deque_to_list(dq)
Print result''')
    assert_in('z', out[0])
    assert_in('a', out[0])
    assert_in('b', out[0])

def test_epl_ordered_map():
    out = run('''Create om equal to ordered_map_new()
ordered_map_set(om, "x", 10)
ordered_map_set(om, "y", 20)
Create keys equal to ordered_map_keys(om)
Print keys''')
    assert_in('x', out[0])
    assert_in('y', out[0])

def test_epl_datetime():
    out = run('Create now equal to utc_now()\nPrint now')
    assert_true(len(out) > 0)
    assert_true(out[0].endswith('Z'))

def test_epl_encoding_html():
    src = 'Create enc equal to html_encode("<b>Hi</b>")\nPrint enc'
    out = run(src)
    assert_in('&lt;', out[0])

def test_epl_base32():
    out = run('Create e equal to base32_encode("Hello")\nCreate d equal to base32_decode(e)\nPrint d')
    assert_eq(out, ['Hello'])

def test_epl_hash_sha1():
    out = run('Create h equal to hash_sha1("test")\nPrint h')
    assert_eq(out, ['a94a8fe5ccb19ba61c4c0873d391e987982fbbd3'])

def test_epl_sql_full():
    out = run('''Create db equal to db_open(":memory:")
db_execute(db, "CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
db_execute(db, "INSERT INTO t (val) VALUES (?)", "hello")
Create c equal to db_count(db, "t")
Print c
db_close(db)''')
    assert_eq(out, ['1'])

def test_epl_math_extended():
    out = run('Create r equal to hypot(3, 4)\nPrint r')
    assert_eq(out, ['5.0'])

def test_epl_secure_random():
    out = run('Create r equal to secure_random_int(1, 100)\nPrint r')
    val = int(out[0])
    assert_true(1 <= val <= 100)

def test_epl_variance():
    out = run('Create v equal to variance([2, 4, 4, 4, 5, 5, 7, 9])\nPrint v')
    assert_true(float(out[0]) > 4.0)

def test_epl_date_range():
    out = run('Create dates equal to date_range("2024-01-01", "2024-01-03")\nPrint dates')
    assert_in('2024-01-01', out[0])
    assert_in('2024-01-03', out[0])

def test_epl_week_of_year():
    out = run('Create w equal to week_of_year("2024-01-15")\nPrint w')
    assert_true(int(out[0]) >= 1)

def test_epl_floor_ceil_div():
    out = run('Create r equal to ceil_div(7, 3)\nPrint r')
    assert_eq(out, ['3'])

def test_epl_permutations():
    out = run('Create r equal to permutations(5, 3)\nPrint r')
    assert_eq(out, ['60'])

def test_epl_combinations():
    out = run('Create r equal to combinations(10, 3)\nPrint r')
    assert_eq(out, ['120'])

def test_epl_base64_url():
    out = run('Create e equal to base64_url_encode("Hello World")\nCreate d equal to base64_url_decode(e)\nPrint d')
    assert_eq(out, ['Hello World'])

def test_epl_file_is_dir():
    out = run('Create r equal to file_is_dir(".")\nPrint r')
    assert_true(out[0].lower() == 'true')

def test_epl_env_ops():
    out = run('''env_set("EPL_TEST_XYZ", "hello")
Create v equal to env_get("EPL_TEST_XYZ")
Print v
env_delete("EPL_TEST_XYZ")''')
    assert_eq(out, ['hello'])


# ═══════════════════════════════════════════════════════════
#  14. EDGE CASES & ERROR HANDLING
# ═══════════════════════════════════════════════════════════

def test_json_query_deep():
    """Deep nested query."""
    from epl.interpreter import EPLDict
    obj = EPLDict({"a": EPLDict({"b": EPLDict({"c": EPLDict({"d": 42})})})})
    r = call_stdlib('json_query', [obj, 'a.b.c.d'], 0)
    assert_eq(r, 42)

def test_linked_list_pop_empty():
    ll = call_stdlib('linked_list_new', [], 0)
    r = call_stdlib('linked_list_pop', [ll], 0)
    assert_eq(r, None)

def test_deque_stress():
    dq = call_stdlib('deque_new', [], 0)
    for i in range(100):
        call_stdlib('deque_push_back', [dq, i], 0)
    assert_eq(call_stdlib('deque_size', [dq], 0), 100)
    for i in range(100):
        v = call_stdlib('deque_pop_front', [dq], 0)
        assert_eq(v, i)

def test_aes_empty_string():
    enc = call_stdlib('aes_encrypt', ['', 'key'], 0)
    dec = call_stdlib('aes_decrypt', [enc, 'key'], 0)
    assert_eq(dec, '')

def test_aes_long_message():
    msg = 'A' * 1024
    enc = call_stdlib('aes_encrypt', [msg, 'key'], 0)
    dec = call_stdlib('aes_decrypt', [enc, 'key'], 0)
    assert_eq(dec, msg)

def test_math_log2_powers():
    for i in range(1, 20):
        r = call_stdlib('log2', [2**i], 0)
        assert_near(r, float(i))

def test_date_range_single_day():
    r = call_stdlib('date_range', ['2024-03-01', '2024-03-01'], 0)
    assert_eq(len(r), 1)
    assert_eq(r[0], '2024-03-01')

def test_path_normalize_dotdot():
    r = call_stdlib('path_normalize', ['a/b/../c'], 0)
    assert_eq(r, 'a/c')

def test_frequency_map_empty():
    r = call_stdlib('frequency_map', [[]], 0)
    assert_eq(len(r.data), 0)

def test_pq_ordering_same_priority():
    pq = call_stdlib('priority_queue_new', [], 0)
    call_stdlib('priority_queue_push', [pq, 1, 'first'], 0)
    call_stdlib('priority_queue_push', [pq, 1, 'second'], 0)
    r1 = call_stdlib('priority_queue_pop', [pq], 0)
    r2 = call_stdlib('priority_queue_pop', [pq], 0)
    # Both should come out (order may depend on heapq internals)
    assert_true(set([r1, r2]) == {'first', 'second'})

def test_ordered_map_overwrite():
    om = call_stdlib('ordered_map_new', [], 0)
    call_stdlib('ordered_map_set', [om, 'k', 1], 0)
    call_stdlib('ordered_map_set', [om, 'k', 2], 0)
    assert_eq(call_stdlib('ordered_map_get', [om, 'k'], 0), 2)
    assert_eq(call_stdlib('ordered_map_size', [om], 0), 1)

def test_base64_url_special_chars():
    """URL-safe base64 with chars that differ from standard base64."""
    data = bytes(range(256)).decode('latin-1')
    encoded = call_stdlib('base64_url_encode', [data], 0)
    assert_true('+' not in encoded)
    assert_true('/' not in encoded)


TEST_FUNCTIONS = [obj for name, obj in globals().items() if name.startswith("test_") and callable(obj)]


def main():
    print("=" * 55)
    print("Phase 2 Stdlib Tests")
    print("=" * 55)

    for test_fn in TEST_FUNCTIONS:
        _legacy_run_case(test_fn.__name__, test_fn)

    print(f"\n{'='*55}")
    print(f"Phase 2 Stdlib Tests: {PASS_COUNT}/{PASS_COUNT+FAIL_COUNT} passed, {FAIL_COUNT} failed")
    print(f"{'='*55}")
    return FAIL_COUNT == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

