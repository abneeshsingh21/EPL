
# EPL - English Programming Language v7.0 🇬🇧

**Write code in plain English. Build anything — software, websites, Android apps, and more.**

### Why EPL?

| Task | C++ | Java | Python | **EPL** |
|------|-----|------|--------|---------|
| Print | `std::cout << "Hi";` | `System.out.println("Hi");` | `print("Hi")` | **`Say "Hi"`** |
| Variable | `int x = 10;` | `int x = 10;` | `x = 10` | **`Set x To 10`** |
| Condition | `if (x > 5) {` | `if (x > 5) {` | `if x > 5:` | **`If x Is Greater Than 5 Then`** |
| Loop | `for(int i=0;i<10;i++)` | `for(int i=0;i<10;i++)` | `for i in range(10):` | **`Repeat 10 Times`** |
| Function | `void greet() {` | `void greet() {` | `def greet():` | **`Define Function greet`** |

> **EPL reads like English, compiles like C, and deploys like Python.**

EPL is an English-syntax programming language with multiple execution backends and a broad tooling surface. It compiles to native executables, transpiles to JavaScript/Node.js/Kotlin, and ships a large standard library (725 Python-backed functions + 21 native EPL modules), a bytecode VM, package manager, web/server tooling, debugger, LSP server, VS Code extension, testing tools, static type system, WSGI/ASGI adapters, and async I/O.

> **53 test files** | **21 native EPL modules** | **725 stdlib functions** | **48 CLI commands** | **51 builtin packages** | **Static type system** | **Full IDE tooling** | **VS Code Extension**

## 🚀 Quick Start

epl hello.epl              # via pip install
python main.py examples/hello.epl   # from source

# Start interactive REPL
epl repl

# Compile to native executable
epl build examples/hello.epl

# Transpile to JavaScript
epl js examples/hello.epl

# Transpile to Node.js
epl node examples/hello.epl

# Transpile to Kotlin
epl kotlin examples/hello.epl

# Generate Android project
epl android examples/hello.epl

# Type-checked execution
epl run examples/hello.epl --strict

# List available standard library modules
epl modules

# Package Manager
epl init                                 # Initialize project
epl new myapp --template web             # Create a supported web starter
epl new mylib --template lib             # Create a reusable library starter
epl install epl-math                     # Install registry package
epl install epl-web                      # Install supported official web facade
epl install user/repo                    # Install GitHub package shorthand
epl gitinstall epl-lang/web-kit web-kit  # Save GitHub dependency to epl.toml
epl pyinstall yaml pyyaml>=6             # Save Python package for `Use python`
epl search web                           # Search local + indexed packages
epl outdated                             # Show newer package versions
epl update --major                       # Allow major-version package upgrades
epl audit                                # Verify lockfile and package integrity
epl packages                             # List packages
epl pydeps                               # List declared Python dependencies
epl gitdeps                              # List declared GitHub dependencies

# GitHub project workflows
epl github clone epl-lang/epl
epl github pull
epl github push . -m "Update project"

# Debugger — step-through debugging
epl debug examples/hello.epl

# Testing — run EPL test suites
epl test tests/

# Linter — check code quality
epl lint src/
epl lint src/ --fix                      # auto-fix issues

# Documentation — generate API docs
epl docs src/

# Formatter — check or rewrite EPL source formatting
epl fmt src/ --check
epl fmt src/ --in-place

# LSP Server — IDE integration
epl lsp                                  # stdio mode (VS Code)

# AI Code Assistant (requires Ollama)
epl ai "write a fibonacci function"

# Bytecode VM — fast execution engine
epl vm examples/hello.epl

# Package into standalone executable
epl package examples/hello.epl

# Start production web server
epl serve examples/webapp.epl
epl serve examples/webapp.epl --port 8080 --reload
epl serve examples/webapp.epl --store sqlite --session redis
```

When you are inside a project directory with `epl.toml`, file-based commands can use the manifest entrypoint directly:

```bash
epl run
epl build
epl serve
```

Starter project templates are available directly from the CLI:

```bash
epl new myapp --template basic
epl new myapp --template cli
epl new myapp --template web
epl new myapp --template api
epl new myapp --template lib
```

## Supported Official Packages

EPL now ships thin supported facade packages for common production workflows:

- `epl-web` - supported web app facade over EPL's current web/runtime features
- `epl-db` - supported database facade over EPL's current DB runtime features
- `epl-test` - supported testing facade for assertions and test summaries

Install them like ordinary packages:

```bash
epl install epl-web
epl install epl-db
epl install epl-test
```

## 🎯 Build Targets

| Target | Command | Output |
|--------|---------|--------|
| Interpreter | `epl file.epl` | Direct execution |
| Type-checked | `epl run file.epl --strict` | Execution with static type checking |
| Native | `epl build file.epl` | Native executable via LLVM + system C compiler |
| JavaScript | `epl js file.epl` | `.js` for browsers |
| Node.js | `epl node file.epl` | `.node.js` for servers |
| Kotlin | `epl kotlin file.epl` | `.kt` for JVM |
| Android | `epl android file.epl` | Android Studio project |
| Debugger | `epl debug file.epl` | Interactive debugging |
| Test Runner | `epl test dir/` | Run EPL test suites |
| Linter | `epl lint dir/` | Code quality check |
| Docs | `epl docs dir/` | HTML/MD/JSON docs |
| LSP | `epl lsp` | IDE language server |
| Bytecode VM | `epl vm file.epl` | Fast VM execution |
| Package | `epl package file.epl` | Standalone executable |
| Serve | `epl serve file.epl` | Production web server |

## Reference Apps

EPL now ships maintained reference targets that are exercised in CI:

- `apps/reference-backend-api` - backend API service with EPL WebApp routes and SQLite-backed data
- `apps/reference-fullstack-web` - server-rendered web app with JSON APIs, CLI `epl serve` validation, generated WSGI/ASGI deploy adapter validation, and generated Docker Compose deploy validation
- deployed backend/fullstack services can be monitored with `python scripts/monitor_reference_apps.py --backend-url <url> --fullstack-url <url>`
- `apps/reference-android` - Android project input validated by generation tests, standard Gradle wrapper generation, and dedicated lint, unit-test, debug, and release Gradle validation
- `apps/reference-desktop` - desktop software input validated by generation tests and a dedicated Gradle compile/test build job
- `packages/reference-hello-lib` - reusable package/library install-pack-validate workflow
- [Security Policy](SECURITY.md) - vulnerability reporting and security expectations
- [Release Checklist](docs/release-checklist.md) - required release gates and artifact validation
- [Benchmark Baselines](docs/benchmarks.md) - benchmark suites and release tracking rules
- [Production Roadmap](docs/production-roadmap.md) - remaining work to raise EPL further
- [Migration Guide](docs/migration-guide.md) - move older projects onto the current v7 workflow
- [Troubleshooting](docs/troubleshooting.md) - common fixes for CLI, package, web, Android, and deployment issues

## ✨ What Makes EPL Special?

EPL reads like English sentences while packing the power of Python, C++, and Java:

```
Remember name as "Alice"
Remember scores as [85, 92, 78, 95, 88]

Say "Hello, " + name + "!"

Sort scores
Reverse scores
Say "Top scores: " + scores

Remember best as scores[0]
If best is between 90 and 100 then
    Say name + " got an A!"
End

Remember squared as scores.map(lambda x -> x raised to 2)
Say "Squared: " + squared
```

## 📝 Language Syntax

### Variables — Two Styles

```
Note: English style
Remember age as 25
Remember name as "Abneesh"
Remember isReady as yes

Note: Classic style
Create integer named age equal to 25
age = 25
active = no
```

### Output — Say or Print

```
Say "Hello, World!"
Print "Hello, World!"
Display "Hello, World!"
```

### Input

```
Ask "What is your name?" and store in name
Say "Hello, " + name + "!"
```

### Conditions

```
If age > 18 then
    Say "Adult"
Otherwise
    Say "Minor"
End

Note: English comparisons - pick whichever reads best!
If score is greater than or equal to 90 then
    Say "Grade: A"
End

Note: Simplified comparisons
If name equals "Alice" then
    Say "Hello Alice!"
End

If x not equals 0 then
    Say "Not zero"
End

If age is at least 18 then
    Say "Adult"
End

If tries is at most 3 then
    Say "Keep trying"
End

Note: Range checks
If temperature is between 60 and 80 then
    Say "Pleasant weather!"
End
```

### Loops

```
Repeat 5 times
    Say "Hello!"
End

While count < 10
    Say count
    Increase count by 1
End

For each item in myList
    Say item
End

For i from 1 to 10
    Say i
End

Note: With step
For i from 0 to 100 step 5
    Say i
End
```

### Functions

```
Define function add that takes a and b
    Return a + b
End function

result = call add with 5 and 10
Say result
```

### Lambda Expressions

```
Note: Arrow style
double = lambda x -> x * 2
Say call double with 5

Note: English style
double = given x return x * 2
add = given x, y return x + y
```

### Classes & Inheritance

```
Define class Dog with name and breed
    Define method speak
        Return name + " says Woof!"
    End method
End class

Create Dog called rex with "Rex" and "Labrador"
Say call rex.speak
```

```
Define class Puppy extends Dog with toy
    Define method play
        Return name + " plays with " + toy
    End method
End class
```

### Constructor Arguments (v2.0)

```
Class Person
  Create name equal to "".
  Create age equal to 0.
  Function init takes n, a
    Set name to n.
    Set age to a.
  End Function.
End.

Create p equal to new Person("Alice", 30).
Print p.name.
Print p.age.
```

### Super Calls (v2.0)

```
Class Animal
  Create sound equal to "...".
  Function speak
    Return sound.
  End Function.
End.

Class Dog extends Animal
  Create sound equal to "Woof".
  Function speak
    Return "Dog says: " + sound.
  End Function.
  Function parent_speak
    Return Super.speak().
  End Function.
End.

Create d equal to new Dog().
Print d.speak().
Print d.parent_speak().
```

### Async/Await (v2.0)

```
Async Function fetch_data takes url
  Return "data from " + url.
End Function.

Create result equal to Await fetch_data("https://api.example.com").
Print result.

Async Function compute takes x
  Return x * 2.
End Function.

Print Await compute(21).
```

### Math — English & Symbolic

```
Note: Power operator
result = 2 ** 10
result = 2 raised to 10

Note: Modulo
remainder = 10 % 3
remainder = 10 mod 3

Note: Floor division
result = 7 // 2

Note: Augmented assignment (symbolic)
x += 5
x -= 2
x *= 3
x /= 2
x %= 3

Note: Augmented assignment (English)
Increase x by 5
Decrease x by 2
Multiply x by 3
Divide x by 2
```

### English List Operations (v0.7)

```
Remember fruits as ["banana", "apple", "cherry"]

Add "date" to fruits
Sort fruits
Reverse fruits
Say fruits
```

### Functional Programming

```
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

Note: Map, Filter, Reduce (both lambda and given work)
evens = numbers.filter(given x return x mod 2 equals 0)
doubled = numbers.map(given x return x * 2)
total = numbers.reduce(given acc, x return acc + x, 0)

Note: Find, Every, Some
first_big = numbers.find(lambda x -> x > 5)
all_positive = numbers.every(lambda x -> x > 0)
has_ten = numbers.some(lambda x -> x == 10)
```

### String Methods

```
text = "  Hello, World!  "
Say text.trim()
Say text.upper()
Say text.lower()
Say text.contains("World")
Say text.replace("World", "EPL")
Say text.split(", ")
Say text.starts_with("Hello")
Say text.reverse()
Say text.repeat(3)
```

### Ternary Expressions

```
status = "adult" if age >= 18 otherwise "minor"
```

### Slicing

```
items = [1, 2, 3, 4, 5]
Say items[1:3]
Say items[:3]
Say items[2:]
Say items[::2]

text = "Hello"
Say text[1:4]
```

### Maps (Dictionaries)

```
person = Map("name" => "Alice", "age" => 30)
Say person["name"]
Say person.keys()
Say person.has("name")
```

### Enums

```
Enum Color
    RED
    GREEN
    BLUE
End

Say Color.RED
```

### Error Handling

```
Try
    result = 10 / 0
Catch error
    Say "Error: " + error
End

Throw "Something went wrong"
```

### Try / Catch / Finally (v4.0)

```
Try
    Create result equal to 10 / 0.
Catch error
    Print "Caught: " + error.
Finally
    Print "Cleanup done.".
End.
```

### Interfaces (v4.0)

```
Interface Drawable
    Function render takes nothing.
    Function resize takes width and height.
End.

Class Circle implements Drawable
    Create radius equal to 5.

    Function render takes nothing
        Print "Drawing circle r=" + radius.
    End Function.

    Function resize takes width and height
        Set radius to width.
    End Function.
End.
```

### Modules (v4.0)

```
Module MathUtils
    Function double takes x
        Return x * 2.
    End Function.

    Function triple takes x
        Return x * 3.
    End Function.

    Export double.
    Export triple.
End.

Print MathUtils::double(5).
Print MathUtils::triple(3).
```

### Static Methods (v4.0)

```
Class MathHelper
    Static Function add takes a and b
        Return a + b.
    End Function.
End.

Print MathHelper.add(3, 4).
```

### Visibility Modifiers (v4.0)

```
Class Account
    Private Create balance equal to 0.
    Public Create owner equal to "".

    Public Function deposit takes amount
        Set balance to balance + amount.
    End Function.

    Private Function validate takes nothing
        Return balance >= 0.
    End Function.
End.
```

### Abstract Methods (v4.0)

```
Class Shape
    Abstract Function area takes nothing.
End.

Class Square extends Shape
    Create side equal to 5.
    Function area takes nothing
        Return side * side.
    End Function.
End.
```

### Constants (v4.0)

```
Constant PI = 3.14159.
Constant APP_NAME = "MyApp".
Constant MAX_RETRIES = 3.

Print PI.
Print APP_NAME.
```

### Yield / Generators (v4.0)

```
Function count_up takes limit
    Create i equal to 0.
    While i < limit
        Yield i.
        Increase i by 1.
    End.
End Function.
```

### Type Annotations (v4.0)

```
Note: EPL supports optional static type checking via --strict flag
Note: Type annotations on variables
Create integer named count equal to 0.
Create text named greeting equal to "Hello".
Create decimal named pi equal to 3.14.
Create boolean named active equal to yes.
```

### File I/O

```
Write "Hello" to file "output.txt"
content = Read file "output.txt"
Say content
```

### Template Strings & String Interpolation

```
name = "EPL"
version = 7
Say "Welcome to {name} version {version}!"

Note: v1.1 - Dollar interpolation with expressions
x = 10
y = 20
Say "Sum: ${x + y}"
Say "Hello, $name!"
```

### Multi-line Strings (v1.1)

```
Create poem equal to """
Roses are red,
Violets are blue,
EPL is awesome,
And so are you!
""".
Print poem.
```

### Default Parameters (v1.1)

```
Function greet takes name, greeting = "Hello"
    Print "$greeting, $name!".
End Function.

Call greet with "Alice".
Call greet with "Bob" and "Hi".
```

### Imports & Libraries

```
Import "helpers.epl"

Note: Python library bridge
Use math
result = call math.sqrt with 16
```

### Web Framework

```
Create WebApp called myApp
Route "/" renders "index.html"
Route "/about" renders "about.html"
Start myApp on port 3000
```

### Comments

```
Note: This is a comment and will be ignored
```

## 🗂 Project Structure

```
EPL/
├── epl/
│   ├── tokens.py           # Token definitions (~200 types, 21 new in v4)
│   ├── lexer.py            # Tokenizer with multi-word keywords
│   ├── ast_nodes.py        # 82 AST node classes (15 new in v4)
│   ├── parser.py           # Recursive-descent parser (75+ methods)
│   ├── interpreter.py      # Tree-walking interpreter (async, constructors, super, modules)
│   ├── compiler.py         # LLVM compilation backend (type inference, classes, closures)
│   ├── runtime.c           # C runtime v3.0 (exceptions, arena alloc, 80+ functions)
│   ├── stdlib.py           # Python-backed standard library (378 functions, ~3600 lines)
│   ├── stdlib/             # Native EPL standard library modules (v4.2)
│   │   ├── registry.json   # Module registry (descriptions, paths)
│   │   ├── math.epl        # Math (factorial, fibonacci, prime, statistics)
│   │   ├── string.epl      # String manipulation (capitalize, slug, pad, truncate)
│   │   ├── collections.epl # Data structures (flatten, chunk, unique, stack, queue)
│   │   ├── functional.epl  # FP tools (map_list, filter_list, reduce_list, compose, pipe)
│   │   ├── datetime.epl    # Date/time utilities (format_duration, time_ago)
│   │   ├── crypto.epl      # Cryptographic helpers (md5, sha256, base64, uuid)
│   │   ├── http.epl        # HTTP client (http_fetch, parse_json, encode_url)
│   │   ├── io.epl          # File/console I/O (read_whole_file, write_whole_file)
│   │   └── testing.epl     # Test framework (test, expect_equal, test_summary)
│   ├── environment.py      # Variable scope manager
│   ├── errors.py           # Error hierarchy with hints (16 error classes, E0100-E1600)
│   ├── cli.py              # CLI entry point for `epl` command (pip install)
│   ├── html_gen.py         # HTML template engine
│   ├── web.py              # Web framework v3.0 (auth, WebSocket, HTTPS, CSRF, HSTS)
│   ├── wsgi.py             # WSGI/ASGI server (v4.0 — production deployment)
│   ├── js_transpiler.py    # EPL → JavaScript / Node.js transpiler v4.0 (interfaces, modules)
│   ├── kotlin_gen.py       # EPL → Kotlin / Android project generator v4.0 (interfaces, modules)
│   ├── gui.py              # Desktop GUI framework (tkinter)
│   ├── package_manager.py  # Package manager v4.0 (registry, lockfile, 36 packages)
│   ├── registry.json       # Shipped package registry
│   ├── lsp_server.py       # Language Server Protocol implementation
│   ├── ai.py               # AI assistant (Groq/Ollama integration)
│   ├── vm.py               # Bytecode virtual machine (compile & run)
│   ├── type_system.py      # Static type system v4.0 (13 type kinds, type checker)
│   ├── async_io.py         # Async I/O v4.0 (event loop, channels, task groups)
│   ├── profiler.py         # Profiler & DAP debugger v4.0 (Chrome Tracing export)
│   ├── database_real.py    # Real SQLite database (ORM, migrations, pooling)
│   ├── networking.py       # TCP/UDP/HTTP networking (DNS, sockets, HTTP client)
│   ├── concurrency_real.py # Real concurrency (threads, channels, atomics, barriers)
│   ├── packager.py         # Cross-platform packager (standalone executables)
│   ├── database.py         # Simple database facade
│   ├── concurrency.py      # Simple concurrency facade
│   ├── debugger.py         # Interactive step-through debugger
│   ├── doc_linter.py       # Documentation generator & code linter
│   └── test_framework.py   # Native EPL testing framework
├── epl-vscode/             # VS Code extension (syntax, snippets, LSP client)
├── main.py                 # CLI entry point (from source: python main.py)
├── examples/               # 18+ sample programs
├── docs/                   # Documentation (language ref, tutorials, architecture)
└── tests/                  # 271 automated tests
```

## 📚 Standard Library

EPL ships with **378 Python-backed functions** available without imports, plus **9 native EPL modules** loadable via `Import "name"`. Run `epl modules` to list them.

### Native EPL Modules (v4.2)

```
Import "math"              Note: factorial, fibonacci, prime, gcd, lcm, statistics
Import "string"            Note: capitalize, slug, pad, truncate, word_count
Import "collections"       Note: flatten, chunk, unique, zip_pair, stack, queue
Import "functional"        Note: map_list, filter_list, reduce_list, compose, pipe
Import "datetime"          Note: format_duration, time_ago, is_weekend, days_until
Import "crypto"            Note: md5, sha256, base64_enc/dec, uuid, random_string
Import "http"              Note: http_fetch, http_send, parse_json, encode_url
Import "io"                Note: read_whole_file, write_whole_file, file_lines
Import "testing"           Note: test, expect_equal, expect_true, test_summary
```

### Built-in Functions (no import needed)

### DateTime

```
Create now_time equal to now().
Create today_date equal to today().
Create yr equal to year("2024-06-15T10:00:00").
Create formatted equal to date_format("2024-01-15T10:30:00", "%Y-%m-%d").
Print is_leap_year(2024).
Print days_in_month(2024, 2).
```

### Crypto & Encoding

```
Create hash1 equal to hash_sha256("hello").
Create hash2 equal to hash_md5("hello").
Create id equal to uuid().
Create encoded equal to base64_encode("Hello World").
Create decoded equal to base64_decode(encoded).
Create hex equal to hex_encode("AB").
```

### Regex

```
Print regex_test("[0-9]+", "abc123").
Create matches equal to regex_find_all("[0-9]+", "a1b2c3").
Create replaced equal to regex_replace("[0-9]", "#", "a1b2c3").
Create parts equal to regex_split(",", "a,b,c").
```

### Math (Extended)

```
Print pi().
Print euler().
Print factorial(12).
Print gcd(12, 8).
Print lcm(4, 6).
Print clamp(15, 0, 10).
Print sign(-5).
Print degrees(pi()).
Print radians(180).
Print lerp(0, 10, 0.5).
Print is_finite(42).
Print atan(1).
Print asin(0.5).
Print acos(0.5).
```

### Collections

```
Create s equal to set_create(1, 2, 2, 3, 3).
Print length(s).

Create zipped equal to zip_lists([1, 2, 3], ["a", "b", "c"]).
Create indexed equal to enumerate_list(["x", "y", "z"]).
Create merged equal to dict_merge(Map with x = 1, Map with y = 2).
```

### Database (SQLite)

```
Create db equal to db_open("myapp.db").
db_create_table(db, "users", "name TEXT, age INTEGER").
db_execute(db, "INSERT INTO users VALUES (?, ?)", ["Alice", 30]).
Create rows equal to db_query(db, "SELECT * FROM users").
Create row equal to db_query_one(db, "SELECT * FROM users WHERE name = ?", ["Alice"]).
Create id equal to db_insert(db, "users", Map with name = "Bob" and age = 25).
db_close(db).
```

### File System

```
Create exists equal to file_exists("test.txt").
Create info equal to file_info("test.txt").
Create files equal to list_dir(".").
Create tmp equal to temp_file().
Create parts equal to path_split("/home/user/file.txt").
Create abs_path equal to path_absolute(".").
```

### URL & Network

```
Create encoded equal to url_encode("hello world").
Create decoded equal to url_decode("hello%20world").
Create parsed equal to url_parse("https://example.com:8080/path?q=1").
```

### CSV

```
Create data equal to csv_parse("name,age\nAlice,30\nBob,25").
Print length(data).
```

### OS & System

```
Print platform().
Create t equal to timer_start("bench").
Create elapsed equal to timer_stop("bench").
Print memory_usage().
```

### Format

```
Print format("Hello, {}! You are {} years old.", "Alice", 30).
```

### Real Database (v3.0 — SQLite with ORM, Migrations, Pooling)

```
Note: Connect and create tables
Create db equal to real_db_connect("myapp.db", "main").
real_db_create_table(db, "users", Map("name" => "TEXT NOT NULL", "age" => "INTEGER")).

Note: CRUD operations
Create id equal to real_db_insert(db, "users", Map("name" => "Alice", "age" => 30)).
Create users equal to real_db_query(db, "SELECT * FROM users").
Create alice equal to real_db_query_one(db, "SELECT * FROM users WHERE name = ?", ["Alice"]).
Create user equal to real_db_find_by_id(db, "users", 1).
real_db_update(db, "users", Map("age" => 31), Map("name" => "Alice")).
real_db_delete(db, "users", Map("name" => "Bob")).
Create count equal to real_db_count(db, "users").

Note: Transactions
real_db_begin(db).
real_db_insert(db, "users", Map("name" => "Charlie", "age" => 25)).
real_db_commit(db).

Note: ORM-style models
real_db_model_define(db, "product", Map("name" => "TEXT NOT NULL", "price" => "REAL")).
real_db_model_create(db, "product", Map("name" => "Widget", "price" => 9.99)).
Create products equal to real_db_model_all(db, "product").

Note: Schema migrations
real_db_migrate(db, 1, "ALTER TABLE users ADD COLUMN email TEXT").

real_db_close(db).
```

### Real Networking (v3.0 — TCP, UDP, HTTP, DNS)

```
Note: DNS and hostname utilities
Create ip equal to net_dns_lookup("example.com").
Create hostname equal to net_hostname().
Create local equal to net_local_ip().
Create open equal to net_is_port_open("localhost", 8080).

Note: HTTP client
Create client equal to net_http_create("https://api.example.com").
Create response equal to net_http_get(client, "/users").
Create post_resp equal to net_http_post(client, "/users", Map("name" => "Alice")).
net_http_close(client).

Note: TCP sockets
Create conn equal to net_tcp_connect("example.com", 80).
net_tcp_send(conn, "GET / HTTP/1.0\r\n\r\n").
Create data equal to net_tcp_receive(conn).
net_tcp_close(conn).

Note: UDP sockets
Create sock equal to net_udp_create().
net_udp_send_to(sock, "127.0.0.1", 5000, "Hello").
net_udp_close(sock).
```

### Real Concurrency (v3.0 — Threads, Channels, Atomics, Barriers)

```
Note: Threads
Create t equal to real_thread_run(myFunction).
real_thread_join(t).
Create count equal to real_cpu_count().

Note: Thread pools
Create pool equal to real_pool_create(4).
real_pool_submit(pool, myTask).
Create results equal to real_pool_map(pool, myFunction, [1, 2, 3, 4]).
real_pool_shutdown(pool).

Note: Mutex (mutual exclusion)
Create lock equal to real_mutex_create().
real_mutex_lock(lock).
Note: ... critical section ...
real_mutex_unlock(lock).

Note: Read-write locks
Create rw equal to real_rwlock_create().
real_rwlock_read_lock(rw).
real_rwlock_read_unlock(rw).

Note: Channels (Go-style message passing)
Create ch equal to real_channel_create(10).
real_channel_send(ch, "hello").
Create msg equal to real_channel_receive(ch).
real_channel_close(ch).

Note: Atomic operations
Create counter equal to real_atomic_int_create(0).
real_atomic_int_increment(counter).
Create val equal to real_atomic_int_get(counter).

Note: Barriers and WaitGroups
Create barrier equal to real_barrier_create(3).
Create wg equal to real_waitgroup_create().
real_waitgroup_add(wg, 1).
Note: ... spawn work ...
real_waitgroup_done(wg).
real_waitgroup_wait(wg).

Note: Parallel helpers
Create results equal to real_parallel_map(myFunc, [1, 2, 3, 4]).
real_parallel_for_each(processItem, items).
```

### Bytecode VM (v3.0 — Fast Execution Engine)

```
Note: Run EPL code via bytecode VM (faster than tree-walking)
Create result equal to vm_run("Set x to 42. Show x.").

Note: Compile to bytecode (for inspection or serialization)
Create bytecode equal to vm_compile("Set x to 10.").

Note: Disassemble bytecode for debugging
Create listing equal to vm_disassemble("Set x to 5.").
Print listing.
```

### WebServer (Flask-powered — 25 functions)

```
Note: Create and configure a web server
app = web_create("myapp")
web_set_cors(app, "*")

Note: Define routes
Define handler as Function()
    Return web_json(Map with message = "Hello, World!")
End Function
web_get(app, "/api/hello", handler)

Note: Route with URL parameters
Define user_handler as Function(id)
    Return web_json(Map with user_id = id)
End Function
web_get(app, "/api/users/<id>", user_handler)

Note: POST route with request data
Define create_handler as Function()
    data = web_request_data()
    Return web_json(Map with created = true)
End Function
web_post(app, "/api/items", create_handler)

Note: Middleware (runs before every request)
Define logger as Function()
    Print "Request received: " + web_request_method() + " " + web_request_path()
End Function
web_middleware(app, logger)

Note: Sessions
web_session_set("user", "alice")
user = web_session_get("user", "anonymous")
web_session_clear()

Note: Request helpers
param = web_request_param("id", "default")
header = web_request_header("Content-Type")
method = web_request_method()
path = web_request_path()
args = web_request_args()

Note: Responses
web_json(Map with key = "value")
web_html("<h1>Hello</h1>")
web_redirect("/other-page")

Note: Start server (foreground or background)
web_start(app, "localhost", 5000, true)
web_start(app, "localhost", 5000, false, true)  Note: background mode
```

### Desktop GUI (Tkinter-powered — 38 functions)

```
Note: Create a window
win = gui_window("My App", 800, 600)

Note: Labels and inputs
gui_label(win, "Enter your name:")
name_input = gui_input(win, "placeholder text")
text_area = gui_text(win, 10, 40)

Note: Buttons with callbacks
Define on_click as Function()
    name = gui_get_value(name_input)
    gui_messagebox("info", "Hello", "Hello, " + name + "!")
End Function
gui_button(win, "Click Me", on_click)

Note: Checkboxes, dropdowns, sliders
cb = gui_checkbox(win, "Accept terms", my_callback)
dd = gui_dropdown(win, ["Option 1", "Option 2", "Option 3"], on_select)
sl = gui_slider(win, 0, 100, on_change)

Note: Layout with frames and grid
frame = gui_frame(win)
gui_grid(label1, 0, 0)
gui_grid(input1, 0, 1)
gui_pack(button1)
gui_place(widget, 100, 200)

Note: Canvas drawing
canvas = gui_canvas(win, 400, 300, "white")
gui_draw_rect(canvas, 10, 10, 100, 100, "blue", "lightblue")
gui_draw_circle(canvas, 200, 150, 50, "red", "pink")
gui_draw_line(canvas, 0, 0, 400, 300, "green", 2)
gui_draw_text(canvas, 200, 150, "Hello!", "black", 14)

Note: Menus with submenus
menu = gui_menu(win)
file_sub = gui_submenu(menu, "File")
gui_menu_item(file_sub, "Open", open_handler)
gui_menu_item(file_sub, "Save", save_handler)

Note: Tabs (notebook)
notebook = gui_tab(win)
tab1 = gui_tab_add(notebook, "Settings")
tab2 = gui_tab_add(notebook, "About")
gui_label(tab1, "Settings go here")
gui_label(tab2, "About page")

Note: Lists and tables
lst = gui_list(win, ["Item 1", "Item 2", "Item 3"], 10)
gui_list_on_select(lst, on_item_selected)
tbl = gui_table(win, ["Name", "Age"], [["Alice", 30], ["Bob", 25]])

Note: Progress bar
progress = gui_progress(win, 100, 0)

Note: Styling
gui_style(widget, "bg", "blue")
gui_style(widget, "fg", "white")
gui_style(widget, "font", "Arial 14 bold")

Note: File dialogs
path = gui_file_dialog("open")
save_path = gui_file_dialog("save")

Note: Images (supports GIF natively, PNG/JPG/BMP/WebP via Pillow)
gui_image(win, "photo.png")

Note: Get/set widget values
value = gui_get_value(input_widget)
gui_set_value(input_widget, "new text")

Note: Run the application
gui_run(win)
```

### Python Bridge (Use python)

```
Note: Import any Python library
Use python "math"
Print math.sqrt(144)

Note: Import with alias
Use python "os.path" as path
Print path.exists(".")

Note: Auto-installs missing packages
Use python "requests"
response = requests.get("https://api.github.com")

Note: Deep chaining works
Use python "os"
basename = os.path().basename("a/b/c.txt")
```

For production projects, declare third-party Python dependencies in `epl.toml` so real users can install them predictably:

```toml
[dependencies]
epl-http = "^2.0.0"

[github-dependencies]
web-kit = "epl-lang/web-kit"

[python-dependencies]
requests = "*"
yaml = "pyyaml>=6"
fastapi = "fastapi[all]>=0.115"
```

Then install them with EPL:

```bash
epl pyinstall requests
epl pyinstall yaml pyyaml>=6
epl gitinstall epl-lang/web-kit web-kit
epl install      # installs EPL, GitHub, and Python dependencies from epl.toml
epl pydeps
epl gitdeps
epl github clone epl-lang/epl
epl github pull
epl github push . -m "Update project"
```

## 📋 Feature Summary

### Core Language
- ✅ Variables with type inference & explicit types
- ✅ Integer, decimal, text, boolean, list, map types
- ✅ Arithmetic: `+`, `-`, `*`, `/`, `%`, `**`, `//`
- ✅ Augmented assignment: `+=`, `-=`, `*=`, `/=`, `%=`
- ✅ Comparisons: symbolic & English (`is greater than`, etc.)
- ✅ Conditionals: `If` / `Otherwise If` / `Otherwise` / `End`
- ✅ Loops: `Repeat`, `While`, `For each`, `For from/to/step`
- ✅ Functions, lambdas, recursion, closures
- ✅ Default parameters (v1.1)
- ✅ **Async/Await** — thread-pool concurrency (v2.0)
- ✅ Classes, inheritance, methods, properties
- ✅ **Constructor arguments** — `Function init takes ...` (v2.0)
- ✅ **Super calls** — `Super.method()` and `Super()` (v2.0)
- ✅ Enums, constants, assertions
- ✅ Error handling: `Try` / `Catch` / `Throw`
- ✅ **Try / Catch / Finally** — full exception handling with cleanup (v4.0)
- ✅ **Interfaces** — `Interface` / `implements` with contract enforcement (v4.0)
- ✅ **Modules** — `Module` / `Export` / `Module::member` access (v4.0)
- ✅ **Static methods** — `Static Function` on classes (v4.0)
- ✅ **Visibility modifiers** — `Public` / `Private` / `Protected` (v4.0)
- ✅ **Abstract methods** — `Abstract Function` for base classes (v4.0)
- ✅ **Constants** — `Constant X = value` immutable bindings (v4.0)
- ✅ **Yield / Generators** — `Yield` statement for lazy sequences (v4.0)
- ✅ **Type annotations** — optional static types with `--strict` flag (v4.0)
- ✅ String templates, slicing, 15 string methods
- ✅ String interpolation `${expression}` and `$variable` (v1.1)
- ✅ Multi-line strings `"""..."""` (v1.1)
- ✅ 16 list methods (map, filter, reduce, find, etc.)
- ✅ 6 map methods (keys, get, set, clear, copy, merge)
- ✅ 28 built-in functions
- ✅ File I/O, imports, modules
- ✅ **50+ soft keywords** — use `row`, `column`, `label`, `port`, `start`, etc. as identifiers (v2.0)

### Standard Library — 311 Built-in Functions + 9 Native EPL Modules
- ✅ **DateTime** — now, today, year/month/day, date_format, is_leap_year, days_in_month
- ✅ **Crypto** — SHA256, SHA512, MD5, UUID, Base64 encode/decode, hex encode/decode
- ✅ **Regex** — test, match, find_all, replace, split, escape
- ✅ **Math** — pi, euler, factorial, gcd, lcm, clamp, sign, lerp, degrees, radians, atan/asin/acos, is_finite/is_nan
- ✅ **Collections** — set operations (create, add, remove, union, intersection, difference), zip_lists, enumerate_list, dict_merge, dict_from_lists
- ✅ **Database** — SQLite (open, close, execute, query, query_one, insert, create_table)
- ✅ **FileSystem** — file_exists, file_info, list_dir, temp_file, temp_dir, path_split, path_absolute, path_join
- ✅ **URL** — url_encode, url_decode, url_parse
- ✅ **CSV** — csv_parse, csv_write
- ✅ **OS** — platform, args, env_get, env_set
- ✅ **System** — timer_start, timer_stop, memory_usage, sleep
- ✅ **Format** — format() with positional placeholders
- ✅ **HTTP** — http_get, http_post (requests-based)
- ✅ **Threading** — thread_run, thread_wait
- ✅ **Network** — socket operations

### English Simplicity (v0.7)
- ✅ `Say` — natural alias for Print
- ✅ `Ask` — conversational input prompts
- ✅ `Remember X as Y` — intuitive variable creation
- ✅ `yes` / `no` — natural booleans (aliases for true/false)
- ✅ `raised to` — English power operator
- ✅ `mod` — English modulo (`10 mod 3`)
- ✅ `equals` / `not equals` / `does not equal` — readable comparisons
- ✅ `is at least` / `is at most` — cleaner `>=`, `<=`
- ✅ `is between X and Y` — natural range checks
- ✅ `Multiply X by Y` / `Divide X by Y` — English math statements
- ✅ `given x return expr` — English lambda alternative
- ✅ `Add X to list` / `Sort list` / `Reverse list` — English list ops

### Advanced
- ✅ Python library bridge (`Use math`, `Use json`)
- ✅ LLVM compilation backend (compile to .exe)
- ✅ Interactive REPL

### Web Framework (v3.0)
- ✅ HTTP server with routing & templates
- ✅ Session management (cookie-based, cryptographic IDs)
- ✅ Static file serving with MIME types
- ✅ CORS headers (same-origin default) and middleware support
- ✅ SQLite persistence layer
- ✅ Rate limiting with configurable thresholds & auto-cleanup

## 📖 Documentation

- [Language Reference](docs/language-reference.md) — Complete syntax and built-in function reference
- [Tutorials](docs/tutorials.md) — Step-by-step guides from beginner to advanced
- [Architecture](docs/architecture.md) — Technical overview of the compiler and runtime
- [Package Manager Guide](docs/package-manager.md) — Project initialization, dependencies, publishing
- ✅ PUT/DELETE HTTP methods
- ✅ **Parameterized routes** — `/users/:id` (v3.0)
- ✅ **Auth utilities** — password hashing (PBKDF2-SHA256), timing-safe verification (v3.0)
- ✅ **Input validation** — email, length, HTML sanitization (v3.0)
- ✅ **Gzip compression** (v3.0)
- ✅ **HTTPS/SSL support** (v3.0)
- ✅ **Threaded request handling** (v3.0)
- ✅ **WebSocket support** — RFC 6455 compliant, rooms, broadcast (v3.0)
- ✅ **Async server** — asyncio-based alternative for high concurrency (v3.0)
- ✅ **Security hardening** — CSRF tokens, HSTS, Permissions-Policy, HTML-escaped errors (v3.0)
- ✅ JavaScript transpiler v4.0 (EPL → browser JS, interfaces, modules, try/catch/finally)
- ✅ Node.js transpiler v4.0 (EPL → server-side JS, 40+ stdlib mappings, v4 AST support)

### GUI Framework (v0.6)
- ✅ Desktop windows with dark theme
- ✅ 10 widget types (label, button, input, text area, checkbox, dropdown, canvas, listbox, image, separator)
- ✅ Layout containers (row, column)
- ✅ Menu bar, event handling, canvas drawing
- ✅ Dialogs (message, error, yes/no, text input, file open/save, color picker)

### Android Target (v3.0 / v4.0)
- ✅ Kotlin transpiler v4.0 (EPL → Kotlin, interfaces, modules, try/catch/finally)
- ✅ Android Studio project generator (manifest, layouts, Gradle)
- ✅ Full project scaffolding with Material Design themes
- ✅ **Dynamic UI generation** — widgets map to Android Views (v2.0)
- ✅ **Event binding** — click handlers, lifecycle methods (v2.0)
- ✅ **Gradle wrapper** included in generated projects (v2.0)
- ✅ **RecyclerView** — list rendering with adapters (v3.0)
- ✅ **Navigation** — multi-activity with intent-based routing (v3.0)
- ✅ **Networking** — OkHttp/Retrofit integration, coroutine async (v3.0)
- ✅ **Permissions** — runtime permission requests (v3.0)
- ✅ **Data persistence** — Room database, SharedPreferences (v3.0)

### Package Manager (v3.0 / v4.0)
- ✅ `epl.toml` manifest with dependency tracking (`epl.json` remains supported as a legacy format)
- ✅ Install from URL, GitHub, registry, or local path
- ✅ Uninstall, list packages, auto-resolve dependencies
- ✅ Project initialization
- ✅ **Built-in registry** — 51 standard packages spanning core, web, data, and tooling workflows
- ✅ **Local & remote registry** — ships with registry.json, falls back to remote (v3.0)
- ✅ **Builtin package installation** — `epl install epl-math` generates real EPL code (v3.0)
- ✅ **Module resolution** — `find_package_module()` (v2.0)
- ✅ **Search** — `search_packages()` with keyword matching (v2.0)

### Static Type System (v4.0)
- ✅ **TypeChecker** — optional static analysis pass (`--strict` flag)
- ✅ **13 type kinds** — Primitive, List, Map, Function, Class, Interface, Union, Optional, GenericVar, Tuple, Any, Never, Alias
- ✅ **Type annotations** — `Create integer named x equal to 5`
- ✅ **Type inference** — automatic type deduction from literal values
- ✅ **Assignability checking** — subtype relationships, integer→decimal promotion
- ✅ **Interface structural typing** — classes checked against interface contracts
- ✅ **Union & optional types** — `A | B`, `T?` type expressions
- ✅ **Generic type variables** — `Class Stack<T>` parameterized types
- ✅ **Diagnostics** — returns typed errors and warnings with line/column info
- ✅ **Built-in signatures** — pre-registered types for 20+ stdlib functions

### Async I/O (v4.0)
- ✅ **EPLEventLoop** — singleton asyncio-backed event loop with thread-pool (16 workers)
- ✅ **EPLTask** — async task with status tracking (running/completed/failed/cancelled)
- ✅ **EPLChannel** — Go-style bounded channels for inter-task communication
- ✅ **EPLTaskGroup** — structured concurrency, run multiple tasks, `wait_all()`
- ✅ **EPLTimer / EPLInterval** — one-shot and repeating timers with callbacks
- ✅ **Async utilities** — `async_sleep()`, `async_read_file()`, `async_write_file()`, `async_http_get()`, `async_http_post()`

### WSGI / ASGI Server (v4.0)
- ✅ **EPLWSGIApp** — full WSGI-compatible application (`__call__(environ, start_response)`)
- ✅ **EPLASGIApp** — ASGI wrapper with WebSocket support
- ✅ **Route registration** — decorator and programmatic (`add_route()`)
- ✅ **Parameterized routes** — `/users/:id/posts` URL patterns
- ✅ **Middleware pipeline** — `add_middleware()` for request/response processing
- ✅ **Static file serving** — caching, path traversal prevention
- ✅ **EPLRequest / EPLResponse** — rich HTTP objects with `.json`, `.form`, `.query` properties
- ✅ **Security headers** — X-Content-Type-Options, X-Frame-Options, X-XSS-Protection by default
- ✅ Deploy with Gunicorn, uWSGI, or any WSGI/ASGI server

### Profiler & DAP Debugger (v4.0)
- ✅ **EPLProfiler** — named timers, auto-instrumentation hooks
- ✅ **Profiling report** — sorted by total time, shows calls, total/avg/min/max ms, percentage
- ✅ **Chrome Tracing export** — `export_trace()` for `chrome://tracing` visualization
- ✅ **Per-function stats** — `get_stats()` dict with calls, total_ms, avg_ms, min_ms, max_ms
- ✅ **DAPServer** — Debug Adapter Protocol server (TCP, default port 4711)
- ✅ **DAP commands** — initialize, setBreakpoints, launch, threads, stackTrace, scopes, variables, continue, next, stepIn, stepOut, evaluate, disconnect
- ✅ **Breakpoint management** — line breakpoints with interpreter hooks
- ✅ **Variable inspection** — stack frame tracking, scope-aware variable access

### AI Assistant (v0.9 / v1.3)
- ✅ Ollama integration (local LLM)
- ✅ Groq cloud API integration (v1.3)
- ✅ Code generation, explanation, fixing, improvement
- ✅ Multi-turn conversation support
- ✅ Model management (list, pull)

### Compiler Backend
- ✅ LLVM IR generation via llvmlite
- ✅ **Type inference** — integer, decimal, text hints (v2.0)
- ✅ **Type coercion** — automatic int/float/string conversion (v2.0)
- ✅ **compile_to_executable()** — end-to-end native compilation (v2.0)
- ✅ **Class compilation** — vtable dispatch, method calls, property access (v3.0)
- ✅ **Closure compilation** — captured variables via environment pointers (v3.0)
- ✅ C runtime v3.0 with exception handling (setjmp/longjmp)
- ✅ Arena allocator for memory management
- ✅ Free functions for strings, lists, maps, objects
- ✅ **Expanded runtime** — file I/O (write/append/exists/delete), random, time, sort, JSON serialization, string builder, map operations, assertions (v3.0)
- ✅ 299+ automated tests across 5 test suites

### Debugger (v3.0)
- ✅ Interactive step-through debugging (`python main.py debug program.epl`)
- ✅ Breakpoints — line-based, function-based, conditional, hit count
- ✅ Step into / Step over / Step out / Continue
- ✅ Variable inspection — `print`, `locals`, `globals`, `stack`
- ✅ Watch expressions
- ✅ Source listing around current position

### VS Code Extension (v3.0)
- ✅ **Syntax highlighting** — full TextMate grammar for all EPL constructs
- ✅ **Code snippets** — 25+ snippets (if, for, function, class, routes, etc.)
- ✅ **Run button** — execute EPL files with Ctrl+Shift+R
- ✅ **Commands** — Run, Compile, Transpile (JS/Kotlin), Generate Android, Start Web Server
- ✅ **Language configuration** — auto-closing pairs, folding, indentation
- ✅ **LSP integration** — connects to EPL Language Server for full IDE features

### LSP Server (v3.0)
- ✅ Full Language Server Protocol for IDE integration
- ✅ **Diagnostics** — parse errors + lint warnings (v3.0)
- ✅ **Code completion** — keywords, builtins (50+), user symbols, dot-method completion (v3.0)
- ✅ **Hover info** — function signatures and documentation (v3.0)
- ✅ **Go-to-definition** — navigate to function/class/variable definitions (v3.0)
- ✅ **Document symbols** — outline view of functions, classes, variables (v3.0)
- ✅ **Code formatting** — auto-indentation (v3.0)
- ✅ Stdio and TCP transport (`python main.py lsp [--tcp]`)

### Testing Framework (v3.0)
- ✅ Native EPL testing with `python main.py test tests/`
- ✅ 15 assertion methods (`expect_equal`, `expect_true`, `expect_contains`, `expect_error`, etc.)
- ✅ Mock objects with call tracking and side effects
- ✅ Auto-discover `test_` functions in .epl files
- ✅ Colorized output with pass/fail/skip counts
- ✅ JUnit XML report generation (`--junit-xml report.xml`)

### ORM & Database (v3.0) — fully accessible from EPL
- ✅ `orm_open(dialect, db)`, `orm_close()` — open SQLite/PostgreSQL/MySQL databases
- ✅ `orm_define_model(db, name)`, `orm_add_field(model, name, type)` — model definitions
- ✅ `orm_migrate(db)` — auto-migration (CREATE TABLE, ALTER TABLE)
- ✅ `orm_create()`, `orm_find()`, `orm_find_by_id()`, `orm_update()`, `orm_delete()` — full CRUD
- ✅ `orm_query(db, model)` — chainable query builder (`.where()`, `.order_by()`, `.limit()`, `.join()`)
- ✅ `orm_raw_query()`, `orm_raw_execute()` — raw SQL support
- ✅ `orm_transaction_begin()`, `orm_transaction_commit()`, `orm_transaction_rollback()` — transactions
- ✅ **Connection pooling** — thread-safe pool with health checks (v3.0)
- ✅ SQLite (built-in), PostgreSQL, MySQL support

### Real Database Engine (v3.0) — Production SQLite
- ✅ `real_db_connect()` / `real_db_close()` — named connection management
- ✅ `real_db_create_table()`, `real_db_execute()`, `real_db_query()` — core SQL operations
- ✅ `real_db_insert()`, `real_db_update()`, `real_db_delete()`, `real_db_find_by_id()` — CRUD
- ✅ `real_db_count()`, `real_db_table_exists()` — schema introspection
- ✅ `real_db_begin()`, `real_db_commit()`, `real_db_rollback()` — manual transactions
- ✅ `real_db_model_define()`, `real_db_model_create()`, `real_db_model_all()` — ORM models
- ✅ `real_db_migrate()` — versioned schema migrations
- ✅ Connection pooling, thread-safe, auto-commit control

### Networking (v3.0) — TCP, UDP, HTTP, DNS
- ✅ `net_dns_lookup()`, `net_hostname()`, `net_local_ip()`, `net_is_port_open()` — DNS/discovery
- ✅ `net_tcp_connect()`, `net_tcp_send()`, `net_tcp_receive()`, `net_tcp_close()` — TCP sockets
- ✅ `net_tcp_server_create()`, `net_tcp_server_accept()` — TCP servers
- ✅ `net_udp_create()`, `net_udp_send_to()`, `net_udp_receive_from()` — UDP sockets
- ✅ `net_http_create()`, `net_http_get()`, `net_http_post()`, `net_http_put()`, `net_http_delete()` — HTTP client
- ✅ Context manager support for auto-cleanup

### Real Concurrency (v3.0) — Threads, Channels, Atomics
- ✅ `real_thread_run()`, `real_thread_join()`, `real_cpu_count()` — thread management
- ✅ `real_pool_create()`, `real_pool_submit()`, `real_pool_map()` — managed thread pools
- ✅ `real_mutex_create()`, `real_mutex_lock()`, `real_mutex_unlock()` — mutual exclusion
- ✅ `real_rwlock_create()` — read/write locks for concurrent reads
- ✅ `real_semaphore_create()`, `real_semaphore_acquire()`, `real_semaphore_release()` — counting semaphores
- ✅ `real_channel_create()`, `real_channel_send()`, `real_channel_receive()` — Go-style channels
- ✅ `real_atomic_int_create()`, `real_atomic_int_increment()`, `real_atomic_int_cas()` — atomic integers
- ✅ `real_atomic_bool_create()` — atomic booleans
- ✅ `real_barrier_create()`, `real_barrier_wait()` — synchronization barriers
- ✅ `real_waitgroup_create()`, `real_waitgroup_add()`, `real_waitgroup_done()`, `real_waitgroup_wait()` — wait groups
- ✅ `real_parallel_map()`, `real_parallel_for_each()` — parallel computation helpers
- ✅ `real_event_create()`, `real_event_set()`, `real_event_wait()` — event signaling

### Bytecode VM (v3.0) — Fast Execution Engine
- ✅ `vm_run(code)` — compile and execute EPL via bytecode (~2-5x faster than tree-walking)
- ✅ `vm_compile(code)` — compile to bytecode for inspection
- ✅ `vm_disassemble(code)` — human-readable disassembly output
- ✅ Stack-based architecture with 50+ opcodes
- ✅ Supports variables, arithmetic, control flow, functions, loops, closures
- ✅ Built-in function dispatching

### Cross-Platform Packager (v3.0)
- ✅ `python main.py package file.epl` — package into standalone executable
- ✅ `python bundle.py` — bundle the EPL CLI itself into a standalone executable
- ✅ Interpreter mode (bundles EPL + runtime) and native mode (LLVM compilation)
- ✅ Dependency scanning — auto-detects imports and stdlib usage
- ✅ Cross-platform: Windows (.exe), macOS (.app), Linux (ELF)
- ✅ PyInstaller integration for self-contained distribution
- ✅ Icon embedding, version metadata, UPX compression
- ✅ Build configuration via `epl.toml` project files (`epl.json` legacy fallback)

### Documentation & Linting (v3.0)
- ✅ Doc generator — extracts from EPL source, supports `@param`, `@return`, `@example`, `@since`, `@deprecated`
- ✅ Output formats: HTML (searchable), Markdown, JSON
- ✅ **Linter** — 15+ rules: line length, naming, complexity, unused code, empty blocks (v3.0)
- ✅ **Auto-fix** — trailing whitespace, tab-to-spaces (`--fix`)
- ✅ Configurable rules with JSON config file
- ✅ CLI: `epl docs src/` / `epl lint src/ [--fix]`

## 🗺 Roadmap

| Version | Status | Features |
| ------- | ------ | -------- |
| v0.1 | ✅ Done | Core language (variables, loops, functions) |
| v0.2 | ✅ Done | Classes & OOP, file I/O, string/list methods |
| v0.3 | ✅ Done | Python library bridge (`Import library`) |
| v0.4 | ✅ Done | LLVM compilation backend (compile to .exe) |
| v0.5 | ✅ Done | Web framework, sessions, CORS, JS/Node.js transpiler |
| v0.6 | ✅ Done | Desktop GUI framework (tkinter) |
| v0.7 | ✅ Done | English simplicity, Kotlin transpiler, Android target |
| v0.8 | ✅ Done | Package manager (install, init, dependencies) |
| v0.9 | ✅ Done | AI code assistant (Ollama integration) |
| v1.0 | ✅ Done | Production release — all targets, 271 tests |
| v1.1 | ✅ Done | Standard library (15 modules), string interpolation, multi-line strings, default params |
| v1.2 | ✅ Done | Web framework v2.0 (SQLite, rate limiting), runtime.c v2.0 (exceptions, arena alloc) |
| v1.3 | ✅ Done | JS transpiler v1.0, Groq AI, comprehensive test suite (427 tests) |
| v2.0 | ✅ Done | Async/await, constructors, super calls, web v3.0 (auth, validation, HTTPS), Kotlin v2.0, package manager v2.0, compiler type system, 482 tests |
| v3.0 | ✅ Done | Debugger, LSP server, testing framework, ORM + DB pool, real SQLite database, TCP/UDP/HTTP networking, real concurrency (threads/channels/atomics), bytecode VM, cross-platform packager, LLVM classes & closures, enhanced Android (RecyclerView/Navigation/Room), security hardening (CSRF/HSTS), 29 builtin packages, 311 stdlib functions, 359+ tests |
| v4.0 | ✅ Done | Static type system (`--strict`), interfaces & implements, modules with `::` access, try/catch/finally, constants, static methods, visibility modifiers, abstract methods, yield/generators, type annotations, WSGI/ASGI server, async I/O (event loop, channels, task groups), profiler with Chrome Tracing export, DAP debug server, JS/Kotlin transpiler v4 (interfaces, modules), 36 builtin packages, 82 AST nodes, 200+ token types, 299+ tests |
| v4.1 | ✅ Done | Pluggable store/session backends (Memory/SQLite/Redis), production `serve` command (Waitress/Gunicorn), hot-reload dev server, ASGI WebSocket support, 30 template filters with chaining, `{% set %}` tag, ternary expressions in templates |
| v4.2 | ✅ Done | 9 native EPL stdlib modules (math, string, collections, functional, datetime, crypto, http, io, testing), module registry + `epl modules` CLI, AST caching for imports, persistent REPL history, security hardening (removed shell=True), Python 3.9+ version guard, REPL `.vars` command with function listing, 271 tests |

## 📜 License

EPL is an open-source programming language project.
