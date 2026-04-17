# EPL Standard Library Reference

> EPL v7.4.3 — 725 Python-backed functions plus native EPL stdlib modules

## Categories

### I/O & Display
| Function | Description |
|----------|-------------|
| `Print <expr>` | Display a value to stdout |
| `Display <expr>` | Alias for Print |
| `read_input(prompt)` | Read user input |
| `print_error(msg)` | Print to stderr |

### Math (built-in)
| Function | Description |
|----------|-------------|
| `round(n)` | Round to nearest integer |
| `floor(n)` | Round down |
| `ceil(n)` | Round up |
| `absolute(n)` | Absolute value |
| `power(base, exp)` | Exponentiation |
| `sqrt(n)` | Square root |
| `max(a, b)` | Maximum |
| `min(a, b)` | Minimum |
| `random()` | Random float 0-1 |
| `random_integer(min, max)` | Random integer in range |
| `log(n)` | Natural logarithm |
| `sin(n)`, `cos(n)`, `tan(n)` | Trigonometric functions |
| `asin(n)`, `acos(n)`, `atan(n)` | Inverse trig |
| `atan2(y, x)` | Two-argument arctangent |
| `degrees(rad)`, `radians(deg)` | Angle conversion |
| `gcd(a, b)`, `lcm(a, b)` | Greatest common divisor, least common multiple |
| `factorial(n)` | Factorial |
| `clamp(val, lo, hi)` | Clamp value to range |
| `lerp(a, b, t)` | Linear interpolation |
| `sign(n)` | Sign (-1, 0, 1) |
| `pi`, `euler`, `inf`, `nan` | Math constants |
| `is_finite(n)`, `is_nan(n)` | Number type checks |

### String Functions
| Function | Description |
|----------|-------------|
| `length(s)` | String/list length |
| `uppercase(s)` | Convert to uppercase |
| `lowercase(s)` | Convert to lowercase |
| `trim(s)` | Remove leading/trailing whitespace |
| `contains(s, sub)` | Check if contains substring |
| `replace(s, old, new)` | Replace occurrences |
| `split(s, delim)` | Split string into list |
| `join(list, delim)` | Join list into string |
| `substring(s, start, end)` | Extract substring |
| `starts_with(s, prefix)` | Check prefix |
| `ends_with(s, suffix)` | Check suffix |
| `index_of(s, sub)` | Find position |
| `char_code(s)` | Get character code |
| `from_char_code(n)` | Character from code |
| `format(template, ...)` | String formatting |
| `regex_escape(s)` | Escape regex special chars |

### Type Conversion
| Function | Description |
|----------|-------------|
| `to_integer(val)` | Convert to integer |
| `to_text(val)` | Convert to string |
| `to_decimal(val)` | Convert to float |
| `type_of(val)` | Get type name as string |

### List Functions
| Method | Description |
|--------|-------------|
| `list.add(item)` | Append item |
| `list.push(item)` | Alias for add |
| `list.remove(index)` | Remove at index |
| `list.contains(item)` | Check membership |
| `list.reverse()` | Reverse in place |
| `list.sort()` | Sort in place |
| `sort(list)` | Return sorted copy |
| `reverse(list)` | Return reversed copy |
| `unique(list)` | Remove duplicates |
| `sum(list)` | Sum numeric list |
| `zip_lists(a, b)` | Zip two lists |
| `enumerate_list(list)` | List of [index, value] pairs |
| `dict_from_lists(keys, vals)` | Create map from parallel lists |

### Map Functions
| Function | Description |
|----------|-------------|
| `map.keys()` | Get all keys |
| `map.values()` | Get all values |
| `map.has(key)` | Check if key exists |

### Set Functions
| Function | Description |
|----------|-------------|
| `set_create()` | Create empty set |
| `set_add(set, item)` | Add to set |
| `set_remove(set, item)` | Remove from set |
| `set_contains(set, item)` | Check membership |
| `set_union(a, b)` | Union of sets |
| `set_intersection(a, b)` | Intersection |
| `set_difference(a, b)` | Difference |

### JSON
| Function | Description |
|----------|-------------|
| `json_parse(str)` | Parse JSON string to value |
| `json_stringify(val)` | Convert value to JSON string |
| `json_pretty(val)` | Pretty-print JSON |

### HTTP / Networking
| Function | Description |
|----------|-------------|
| `http_get(url)` | HTTP GET request |
| `http_post(url, data)` | HTTP POST request |
| `http_put(url, data)` | HTTP PUT request |
| `http_delete(url)` | HTTP DELETE request |
| `url_encode(s)`, `url_decode(s)` | URL encoding |
| `dns_lookup(host)` | DNS resolution |
| `is_port_open(host, port)` | Check port availability |

### File System
| Function | Description |
|----------|-------------|
| `file_read(path)` | Read file contents |
| `file_write(path, data)` | Write to file |
| `file_append(path, data)` | Append to file |
| `file_exists(path)` | Check if file exists |
| `file_delete(path)` | Delete file |
| `file_rename(old, new)` | Rename file |
| `file_copy(src, dst)` | Copy file |
| `file_size(path)` | Get file size |
| `file_read_lines(path)` | Read as list of lines |
| `dir_list(path)` | List directory contents |
| `dir_create(path)` | Create directory |
| `dir_delete(path)` | Delete directory |
| `dir_exists(path)` | Check directory exists |
| `path_join(a, b)` | Join path components |
| `path_basename(p)` | Get filename |
| `path_dirname(p)` | Get directory |
| `path_extension(p)` | Get file extension |
| `temp_file()`, `temp_dir()` | Create temporary file/directory |

### Database
| Function | Description |
|----------|-------------|
| `db_open(path)` | Open SQLite database |
| `db_close()` | Close database |
| `db_execute(sql, params)` | Execute SQL |
| `db_query(sql, params)` | Query, return all rows |
| `db_query_one(sql, params)` | Query, return first row |
| `db_insert(table, data)` | Insert record |
| `db_create_table(name, cols)` | Create table |

### Date & Time
| Function | Description |
|----------|-------------|
| `now()` | Current datetime string |
| `today()` | Current date string |
| `sleep(seconds)` | Pause execution |
| `timestamp()` | Unix timestamp |
| `date_format(date, fmt)` | Format date |
| `date_parse(str, fmt)` | Parse date string |
| `date_diff(a, b, unit)` | Difference between dates |
| `year(d)`, `month(d)`, `day(d)` | Extract date parts |
| `hour(d)`, `minute(d)`, `second(d)` | Extract time parts |
| `day_of_week(d)` | Day of week (0=Monday) |
| `is_leap_year(y)` | Check leap year |

### Regex
| Function | Description |
|----------|-------------|
| `regex_match(pattern, str)` | Match regex at start |
| `regex_find(pattern, str)` | Find first match |
| `regex_find_all(pattern, str)` | Find all matches |
| `regex_replace(pattern, repl, str)` | Replace matches |
| `regex_split(pattern, str)` | Split by pattern |
| `regex_test(pattern, str)` | Test if matches |

### Cryptography & Encoding
| Function | Description |
|----------|-------------|
| `hash_md5(s)` | MD5 hash |
| `hash_sha256(s)` | SHA-256 hash |
| `hash_sha512(s)` | SHA-512 hash |
| `base64_encode(s)` | Base64 encode |
| `base64_decode(s)` | Base64 decode |
| `uuid()`, `uuid4()` | Generate UUID |
| `hex_encode(s)`, `hex_decode(s)` | Hex encoding |

### OS & System
| Function | Description |
|----------|-------------|
| `exec(cmd)` | Execute shell command |
| `exec_output(cmd)` | Execute and capture output |
| `env_get(key)` | Get environment variable |
| `env_set(key, val)` | Set environment variable |
| `platform()` | OS name |
| `cpu_count()` | Number of CPUs |
| `memory_usage()` | Memory usage in bytes |
| `cwd()` | Current working directory |
| `chdir(path)` | Change directory |
| `pid()` | Process ID |
| `args()` | Command-line arguments |
| `timer_start()`, `timer_stop()` | Performance timing |

### CSV
| Function | Description |
|----------|-------------|
| `csv_read(path)` | Read CSV file |
| `csv_write(path, data)` | Write CSV file |
| `csv_parse(text)` | Parse CSV string |

### Concurrency
| Function | Description |
|----------|-------------|
| `mutex_create()` | Create mutex lock |
| `mutex_lock(m)`, `mutex_unlock(m)` | Lock/unlock |
| `channel_create(size)` | Create buffered channel |
| `channel_send(ch, val)` | Send to channel |
| `channel_receive(ch)` | Receive from channel |
| `semaphore_create(n)` | Create semaphore |
| `parallel_map(fn, list)` | Map in parallel |
| `thread_pool_create(n)` | Create thread pool |

### ORM (Object-Relational Mapping)
| Function | Description |
|----------|-------------|
| `orm_open(path)` | Open ORM database |
| `orm_define_model(name)` | Define a model |
| `orm_add_field(model, name, type)` | Add field |
| `orm_migrate()` | Run migrations |
| `orm_create(model, data)` | Create record |
| `orm_find(model, query)` | Find records |
| `orm_update(model, id, data)` | Update record |
| `orm_delete(model, id)` | Delete record |

---

## Security Note

When running with `--sandbox` flag, the following functions are **disabled**:
`exec`, `exec_output`, `file_write`, `file_delete`, `file_append`,
`dir_delete`, `dir_create`, `chdir`, `env_set`, `env_get`,
`download`, `http_get`, `http_post`

This prevents untrusted EPL code from modifying the filesystem or making network requests.
