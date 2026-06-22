# EPL Standard Library Reference

EPL v9.7.0 includes Python-backed built-ins plus native EPL modules under `epl/stdlib/`. This page documents the stable surface most useful to application authors and marks optional or environment-dependent areas clearly.

Use implementation tests as the final release gate for any function your product depends on.

---

## I/O And Display

| Function / Statement | Description |
| --- | --- |
| `Print expr` | Print a value |
| `Say expr` | Print alias |
| `Display expr` | Print alias |
| `Show expr` | Print alias |
| `Input name with prompt "..."` | Read user input into variable |
| `Ask "..." store in name` | English input form |
| `read_input(prompt)` | Read user input where available |
| `print_error(msg)` | Print to stderr where available |

---

## Core Types And Conversion

| Function | Description |
| --- | --- |
| `length(x)` | Length of text, list, or map |
| `type_of(x)` | Runtime type name |
| `to_integer(x)` | Convert to integer |
| `to_decimal(x)` | Convert to decimal |
| `to_text(x)` | Convert to text |
| `to_boolean(x)` | Convert to boolean |
| `is_integer(x)` | Integer check |
| `is_decimal(x)` | Decimal check |
| `is_number(x)` | Number check |
| `is_text(x)` | Text check |
| `is_boolean(x)` | Boolean check |
| `is_list(x)` | List check |
| `is_nothing(x)` | Nothing check |

---

## Math

| Function | Description |
| --- | --- |
| `round(n)` | Round number |
| `floor(n)` | Round down |
| `ceil(n)` | Round up |
| `absolute(n)` | Absolute value |
| `power(base, exp)` | Exponentiation |
| `sqrt(n)` | Square root |
| `min(a, b)` | Minimum |
| `max(a, b)` | Maximum |
| `random(min, max)` | Random value in range in the core interpreter |
| `random_integer(min, max)` | Random integer where available in stdlib modules |
| `log(n)` | Natural logarithm |
| `sin(n)`, `cos(n)`, `tan(n)` | Trigonometry |
| `asin(n)`, `acos(n)`, `atan(n)` | Inverse trigonometry |
| `atan2(y, x)` | Two-argument arctangent |
| `degrees(rad)`, `radians(deg)` | Angle conversion |
| `gcd(a, b)`, `lcm(a, b)` | Greatest common divisor / least common multiple |
| `factorial(n)` | Factorial |
| `clamp(value, min, max)` | Clamp value |
| `lerp(a, b, t)` | Linear interpolation |
| `sign(n)` | Sign value |
| `is_finite(n)`, `is_nan(n)` | Number checks |

Math constants such as `pi`, `euler`, `inf`, and `nan` may be available depending on runtime path.

---

## String Functions

| Function | Description |
| --- | --- |
| `uppercase(s)` | Convert to uppercase |
| `lowercase(s)` | Convert to lowercase |
| `trim(s)` | Trim whitespace |
| `contains(s, sub)` | Contains substring |
| `replace(s, old, new)` | Replace occurrences |
| `split(s, delim)` | Split into list |
| `join(list, delim)` | Join list into text |
| `substring(s, start, end)` | Extract substring |
| `starts_with(s, prefix)` | Prefix check |
| `ends_with(s, suffix)` | Suffix check |
| `index_of(s, sub)` | Find position |
| `char_code(s)` | Character code |
| `from_char_code(n)` | Character from code |
| `format(template, ...)` | String formatting |
| `regex_escape(s)` | Escape regex metacharacters |

String method equivalents:

```epl
s = " Hello "
Say s.uppercase()
Say s.lowercase()
Say s.trim()
Say s.contains("ell")
Say s.replace("Hello", "Hi")
Say s.split(" ")
Say s.substring(0, 5)
Say s.starts_with("H")
Say s.ends_with("o")
Say s.index_of("l")
Say s.count("l")
Say s.repeat(2)
Say s.reverse()
Say s.char_at(0)
Say s.to_list()
```

Numeric conversions need a string whose contents are actually a number:

```epl
Say "42".to_integer()
Say "3.14".to_decimal()
```

---

## Lists

| Function / Method | Description |
| --- | --- |
| `range(n)` | List from `0` to `n - 1` |
| `range(start, end)` | Range where supported |
| `sum(list)` | Sum numeric list |
| `sorted(list)` | Sorted copy |
| `reversed(list)` | Reversed copy |
| `append(list, item)` | Append helper where available |
| `remove(list, item)` | Remove helper where available |
| `contains(collection, item)` | Membership helper |
| `list.add(item)` | Append item |
| `list.remove(item)` | Remove first matching value |
| `list.contains(item)` | Membership |
| `list.sort()` | Sort in place |
| `list.reverse()` | Reverse in place |
| `list.join(separator)` | Join as text |
| `list.pop()` | Remove and return last item |
| `list.clear()` | Empty list |
| `list.copy()` | Copy list |
| `list.map(fn)` | Transform values |
| `list.filter(fn)` | Keep matching values |
| `list.reduce(fn)` | Fold values |
| `list.find(fn)` | First matching value |
| `list.every(fn)` | All values match |
| `list.some(fn)` | Any value matches |
| `list.index_of(item)` | Find index |
| `list.count(item)` | Count matches |
| `list.slice(start, end)` | Slice |
| `list.flatten()` | Flatten nested lists |
| `list.unique()` | Unique values |
| `list.sum()`, `list.min()`, `list.max()` | Numeric helpers |

---

## Maps

| Function / Method | Description |
| --- | --- |
| `keys(map)` | Keys list |
| `values(map)` | Values list |
| `map.keys()` | Keys list |
| `map.values()` | Values list |
| `map.entries()` | Entries |
| `map.has(key)` | Key existence |
| `map.get(key, default)` | Read with default |
| `map.set(key, value)` | Set key |
| `map.remove(key)` | Remove key |
| `map.merge(other)` | Merge maps |
| `map.clear()` | Empty map |
| `map.copy()` | Copy map |

Use `Map with key = value and key2 = value2` for literals. Keep literal pairs on one logical line.

---

## Sets

| Function | Description |
| --- | --- |
| `set_create()` | Create empty set |
| `set_add(set, item)` | Add item |
| `set_remove(set, item)` | Remove item |
| `set_contains(set, item)` | Membership |
| `set_union(a, b)` | Union |
| `set_intersection(a, b)` | Intersection |
| `set_difference(a, b)` | Difference |

---

## JSON

| Function | Description |
| --- | --- |
| `json_parse(text)` | Parse JSON text |
| `json_stringify(value)` | Convert value to JSON text |
| `json_pretty(value)` | Pretty-print JSON where available |
| `json_valid(text)` | Validate JSON where available |
| `json_merge(a, b)` | Merge JSON-like maps where available |
| `json_query(value, path)` | Query JSON-like data where available |

```epl
data = json_parse("{\"ok\": true}")
Say json_stringify(Map with ok = True)
```

---

## HTTP And Networking

| Function | Description |
| --- | --- |
| `http_get(url)` | HTTP GET |
| `http_post(url, data)` | HTTP POST |
| `http_put(url, data)` | HTTP PUT |
| `http_delete(url)` | HTTP DELETE |
| `url_encode(s)`, `url_decode(s)` | URL encoding |
| `dns_lookup(host)` | DNS lookup where available |
| `is_port_open(host, port)` | Port check where available |

Network functions may be blocked in sandbox mode.

---

## File System And Paths

| Function | Description |
| --- | --- |
| `file_read(path)` | Read file |
| `file_write(path, data)` | Write file |
| `file_append(path, data)` | Append file |
| `file_exists(path)` | File existence |
| `file_delete(path)` | Delete file |
| `file_rename(old, new)` | Rename file |
| `file_copy(src, dst)` | Copy file |
| `file_size(path)` | File size |
| `file_read_lines(path)` | Read lines |
| `file_write_lines(path, lines)` | Write lines |
| `dir_list(path)` | List directory |
| `dir_create(path)` | Create directory |
| `dir_delete(path)` | Delete directory |
| `dir_exists(path)` | Directory existence |
| `path_join(a, b, ...)` | Join paths |
| `path_basename(path)` | Base name |
| `path_dirname(path)` | Directory name |
| `path_extension(path)` | Extension |
| `path_absolute(path)` | Absolute path |
| `temp_file()`, `temp_dir()` | Temporary paths |

File write/delete functions may be blocked in sandbox mode.

---

## SQLite Database

| Function | Description |
| --- | --- |
| `db_open(path)` | Open SQLite and return connection ID |
| `db_close(db)` | Close connection |
| `db_execute(db, sql[, params])` | Execute SQL |
| `db_query(db, sql[, params])` | Query all rows |
| `db_query_one(db, sql[, params])` | Query first row or `Nothing` |
| `db_insert(db, table, map)` | Insert simple record |
| `db_create_table(db, table, columns)` | Create simple table from type map |
| `db_tables(db)` | List tables where available |

`db_create_table` now accepts standard SQL column constraints and parameterized types in its column map, including `INTEGER PRIMARY KEY`, `TEXT NOT NULL`, `VARCHAR(255)`, and `DECIMAL(10,2)`. Allowed type words include `DECIMAL`, `FLOAT`, `DOUBLE`, `CHAR`, and `TIMESTAMP`. Identifiers are still validated and SQL injection is still blocked.

```epl
db = db_open(":memory:")
db_create_table(db, "products", Map with id = "INTEGER PRIMARY KEY" and name = "VARCHAR(255)" and price = "DECIMAL(10,2)" and qty = "INTEGER NOT NULL")
db_close(db)
```

Production note: use `db_execute` for migrations and parameterized SQL for values.

---

## Additional Database Adapters

| Function | Description |
| --- | --- |
| `real_db_connect(url)` | Connect to PostgreSQL/MySQL/SQLite if supported |
| `real_db_close(db)` | Close adapter connection |
| `real_db_close_all()` | Close all adapter connections |
| `real_db_execute(db, sql[, params])` | Execute SQL |
| `real_db_execute_many(db, sql, params_list)` | Execute many |
| `real_db_query(db, sql[, params])` | Query rows |
| `real_db_query_one(db, sql[, params])` | Query one row |
| `real_db_begin(db)` | Begin transaction where available |
| `real_db_commit(db)` | Commit transaction |
| `real_db_rollback(db)` | Roll back transaction |
| `real_db_create_table(db, table, columns)` | Create table helper |

Validate driver availability and behavior in your deployment environment.

---

## Date And Time

| Function | Description |
| --- | --- |
| `now()` | Current datetime string |
| `today()` | Current date string |
| `sleep(seconds)` | Pause execution |
| `timestamp()` | Unix timestamp |
| `date_format(date, fmt)` | Format date |
| `date_parse(text, fmt)` | Parse date |
| `date_diff(a, b, unit)` | Difference |
| `date_add(date, amount, unit)` | Add duration |
| `year(d)`, `month(d)`, `day(d)` | Date parts |
| `hour(d)`, `minute(d)`, `second(d)` | Time parts |
| `day_of_week(d)` | Day of week |
| `is_leap_year(y)` | Leap-year check |

---

## Regex

| Function | Description |
| --- | --- |
| `regex_match(pattern, text)` | Match at start |
| `regex_find(pattern, text)` | First match |
| `regex_find_all(pattern, text)` | All matches |
| `regex_replace(pattern, repl, text)` | Replace |
| `regex_split(pattern, text)` | Split |
| `regex_test(pattern, text)` | Boolean test |
| `regex_escape(text)` | Escape pattern characters |

---

## Cryptography And Encoding

| Function | Description |
| --- | --- |
| `hash_md5(s)` | MD5 hash |
| `hash_sha256(s)` | SHA-256 hash |
| `hash_sha512(s)` | SHA-512 hash |
| `base64_encode(s)` | Base64 encode |
| `base64_decode(s)` | Base64 decode |
| `uuid()`, `uuid4()` | UUID |
| `hex_encode(s)`, `hex_decode(s)` | Hex encoding |
| `hmac_sha256(key, msg)` | HMAC where available |
| `hmac_sha512(key, msg)` | HMAC where available |

Use password-specific auth helpers for passwords; do not use raw hashes for password storage.

---

## Auth

| Function | Description |
| --- | --- |
| `auth_hash_password(password)` | PBKDF2 password hash |
| `auth_verify_password(password, hash)` | Constant-time password verification |
| `auth_jwt_create(payload, secret[, expiry_seconds])` | Create JWT |
| `auth_jwt_verify(token, secret)` | Verify JWT |
| `auth_jwt_decode(token)` | Decode JWT without verifying |
| `auth_generate_token(length)` | Generate random token |
| `auth_api_key_create(prefix)` | Create API key and hash |
| `auth_api_key_verify(key, stored_hash)` | Verify API key |
| `auth_basic_decode(encoded)` | Decode Basic auth |

Keep secrets out of source code and logs.

---

## WebSocket

| Function | Description |
| --- | --- |
| `ws_server_create(port)` | Create WebSocket server |
| `ws_server_start(server_id)` | Start server |
| `ws_server_stop(server_id)` | Stop server |
| `ws_on_connect(server_id, handler)` | Register connect handler |
| `ws_on_message(server_id, handler)` | Register message handler |
| `ws_on_disconnect(server_id, handler)` | Register disconnect handler |
| `ws_broadcast(server_id, message)` | Broadcast to clients |
| `ws_send_to(server_id, client_id, message)` | Send to one client |
| `ws_room_join(server_id, client_id, room)` | Join room |
| `ws_room_leave(server_id, client_id, room)` | Leave room |
| `ws_room_broadcast(server_id, room, message)` | Broadcast to room |
| `ws_clients(server_id)` | List clients |

Validate behavior behind proxies and load balancers.

---

## Templates

| Function | Description |
| --- | --- |
| `template_render(name[, context])` | Render named template |
| `template_render_string(template[, context])` | Render template string |

Escape user-controlled data unless the template engine explicitly marks it safe.

---

## OS And System

| Function | Description |
| --- | --- |
| `exec(cmd)` | Execute command and return exit code |
| `exec_output(cmd)` | Execute command and capture output |
| `env_get(key[, default])` | Read environment variable |
| `env_set(key, value)` | Set environment variable |
| `env_has(key)` | Check environment variable |
| `env_all()` | Environment map |
| `platform()` | Platform info |
| `cpu_count()` | CPU count |
| `memory_usage()` | Memory usage |
| `cwd()` | Current directory |
| `chdir(path)` | Change directory |
| `pid()` | Process ID |
| `args()` | CLI arguments where available |

Dangerous OS functions are disabled in sandbox mode.

---

## CSV

| Function | Description |
| --- | --- |
| `csv_read(path)` | Read CSV |
| `csv_write(path, data)` | Write CSV |
| `csv_parse(text)` | Parse CSV text |

---

## Concurrency

| Function | Description |
| --- | --- |
| `mutex_create()` | Create mutex |
| `mutex_lock(m)`, `mutex_unlock(m)` | Lock/unlock |
| `channel_create(size)` | Create channel |
| `channel_send(ch, value)` | Send |
| `channel_receive(ch)` | Receive |
| `semaphore_create(n)` | Create semaphore |
| `parallel_map(fn, list)` | Parallel map |
| `thread_pool_create(n)` | Thread pool |
| `real_thread_run(fn, ...)` | Real thread helper where available |
| `real_thread_join(t)` | Join real thread |
| `real_channel_create(size)` | Real channel helper |

Test concurrency behavior under realistic load before production use.

---

## Data Science, ML, Plotting, Cloud

These categories are optional-dependency surfaces.

Examples include:

- `ds_read_csv`, `ds_shape`, `ds_describe`, `ds_sum`, `ds_bar_chart`, `ds_save_plot`
- `ml_load_data`, `ml_split`, `ml_random_forest`, `ml_train`, `ml_accuracy`, `ml_save_model`
- `cloud_s3_upload`, `cloud_s3_download`, `cloud_lambda_invoke`, `cloud_sqs_send`

Production requirements:

- pin Python packages in `epl.toml`
- validate imports during CI
- handle missing backend errors with `Try`/`Catch`
- keep cloud credentials in environment variables or a secret manager

---

## Native EPL Modules

Common modules under `epl/stdlib/` include:

| Module | Purpose |
| --- | --- |
| `math` | Math helpers |
| `string` | String helpers |
| `collections` | Data structures |
| `io` | File/console helpers |
| `testing` | Test helpers |
| `datetime` | Date/time helpers |
| `functional` | Functional helpers |
| `http` | HTTP helpers |
| `crypto` | Crypto/encoding helpers |
| `json` | JSON helpers |
| `auth` | Auth helpers |
| `websocket` | WebSocket helpers |
| `template` | Template helpers |

Import example:

```epl
Import "math" as Math
Import "collections" as Collections
```

---

## Bundled Importable Modules

Six modules ship in `epl/stdlib/` and import cleanly: `json`, `encoding`, `net`, `os`, `regex`, and `sql`. Each is a thin EPL wrapper over the always-available Python-backed built-ins documented above (`json_parse`, `regex_match`, `db_*`, and so on). The built-ins remain callable directly, with or without importing a module.

### Import Semantics

A bare import brings a module's functions in as plain (unqualified) names:

```epl
Import "encoding"
Say to_base64("hi")
Note: prints aGk=
```

An aliased import namespaces the functions under the alias:

```epl
Import "encoding" as ENC
Say ENC.to_base64("hi")
Note: prints aGk=
```

### JSON Import Gotcha

`json` is a reserved token, so member access like `json.parse(...)` will not lex. Use one of these two forms instead:

```epl
Note: Bare import — call functions as plain names.
Import "json"
Say parse("[1,2,3]")
Note: prints [1, 2, 3]
```

```epl
Note: Aliased import (recommended for a namespace).
Import "json" as J
Say J.stringify(Map with a = 1 and b = 2)
Note: prints {"a": 1, "b": 2}
```

### json

| Function | Description |
| --- | --- |
| `parse(value)` | Parse JSON text into a value |
| `stringify(value)` | Serialize a value to JSON text |
| `pretty(value)` | Pretty-print a value as JSON |
| `is_valid(value)` | Boolean JSON-validity check |
| `merge(obj1, obj2)` | Merge two maps |
| `query(obj, path)` | Query a path within JSON-like data |

### encoding

| Function | Description |
| --- | --- |
| `to_base64(value)`, `from_base64(value)` | Base64 encode / decode |
| `to_base64_url(value)`, `from_base64_url(value)` | URL-safe Base64 |
| `to_base32(value)`, `from_base32(value)` | Base32 |
| `to_hex(value)`, `from_hex(value)` | Hex encoding |
| `to_url(value)`, `from_url(value)` | URL (percent) encoding |
| `to_html(value)`, `from_html(value)` | HTML entity encoding |

### net

| Function | Description |
| --- | --- |
| `tcp_open(host, port)` | Open a TCP connection |
| `tcp_write(conn, data)`, `tcp_read(conn)`, `tcp_read_line(conn)` | TCP I/O |
| `tcp_disconnect(conn)` | Close a TCP connection |
| `udp_open()`, `udp_bind_port(sock, port)` | UDP socket setup |
| `udp_send(sock, host, port, data)`, `udp_recv(sock)` | UDP I/O |
| `fetch(url)` | HTTP GET |
| `post_json(url, data)` | HTTP POST with JSON body |
| `create_server(port)`, `add_route(server, method, path, handler)` | Build a server |
| `start_server(server)`, `stop_server(server)` | Run / stop a server |
| `lookup(host)` | DNS lookup |
| `port_open(host, port)` | Port reachability check |

### os

| Function | Description |
| --- | --- |
| `get_env(name)`, `set_env(name, value)`, `has_env(name)`, `delete_env(name)`, `all_env()` | Environment variables |
| `run(command)`, `run_async(command)`, `kill(pid)` | Process control |
| `get_platform()` | Platform info map (os, version, arch, python, node) |
| `get_arch()`, `get_hostname()`, `get_cpu_count()`, `get_pid()` | System info |
| `get_cwd()`, `home()`, `username()`, `admin()` | Process / user info |

### regex

| Function | Description |
| --- | --- |
| `match(pattern, value)` | Match anchored at the start of the string; returns matched text or nothing |
| `find(pattern, value)` | First match details |
| `find_all(pattern, value)` | List of all matches |
| `replace(pattern, value, replacement)` | Replace matches |
| `split(pattern, value)` | Split by pattern |
| `test(pattern, value)` | Boolean test |
| `escape(value)` | Escape regex metacharacters |
| `compile(pattern, flags)` | Compile a pattern |
| `groups(pattern, value)` | Capture groups |

Note that `match` anchors at the start of the string.

### sql

| Function | Description |
| --- | --- |
| `open(path)`, `close(conn)` | Open / close a connection (`:memory:` for in-memory) |
| `execute(conn, sql)` | Run a statement |
| `query(conn, sql)`, `query_one(conn, sql)` | Read rows |
| `insert(conn, table, record)` | Insert a record |
| `update(conn, table, data, where)` | Update rows |
| `delete(conn, table, where)` | Delete rows |
| `count(conn, table)` | Count rows |
| `tables(conn)`, `table_info(conn, table)` | Schema inspection |
| `create_table(conn, table, schema)` | Create a table |
| `begin(conn)`, `commit(conn)`, `rollback(conn)` | Transactions |
| `backup(conn, dest_path)` | Back up the database |

```epl
Import "sql" as SQL
Create conn equal to SQL.open(":memory:")
SQL.execute(conn, "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
SQL.execute(conn, "INSERT INTO users (name) VALUES ('Alice')")
Say SQL.count(conn, "users")
SQL.close(conn)
Note: prints 1
```

The soft keywords `match`, `fetch`, `delete`, and `where` are what allow `regex.match`, `net.fetch`, `sql.delete`, and `sql ... where` to be used as member names.

---

## Sandbox Notes

When running with `--sandbox`, EPL restricts dangerous capabilities. Expect these categories to be blocked or limited:

- shell execution
- filesystem writes and deletes
- environment mutation
- network requests
- Python, JavaScript, and TypeScript bridges
- selected import paths

Use sandbox mode for untrusted code and tests that exercise user-submitted programs.
