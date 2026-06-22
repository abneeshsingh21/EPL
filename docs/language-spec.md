> **EPL v9.8.0** - English Programming Language
>
> This specification describes the syntax and runtime surface supported by the current EPL source tree. When an older example conflicts with this file, treat this file, the parser, and the tests as the source of truth.

---

## 1. Scope And Support Boundary

EPL is a general-purpose language with plain-English syntax. The current implementation includes:

- Variables, constants, expressions, functions, lambdas, classes, modules, imports, and error handling
- Lists and `Map with ...` dictionaries
- Native WebApp routes with HTML pages and JSON responses
- Built-in SQLite helpers and additional `real_db_*` adapters
- Python, JavaScript, and TypeScript bridge statements
- Standard library modules under `epl/stdlib/`
- CLI targets for interpreter, bytecode VM, JavaScript, Python, Kotlin, Android, iOS, desktop, web, and deployment generation

Enterprise guidance:

- Prefer syntax shown in this document for long-lived code.
- Treat rapidly evolving UI, 3D, ML, cloud, and package-publishing surfaces as integration features that should be validated in CI for your exact target.
- Use parser-verified examples and tests for release gates. Documentation snippets are illustrative unless explicitly marked as production patterns.
- Do not rely on undocumented legacy syntax in new code.

---

## 2. Lexical Structure

### 2.1 Case

Keywords are recognized case-insensitively by the lexer, but examples use title-case statement keywords (`Create`, `If`, `Function`, `Route`) and capitalized built-in literals (`True`, `False`, `Nothing`) for readability.

### 2.2 Comments

```epl
Note: This is a single-line comment

Note "String-form comment, useful as a module header or docstring"
Comment "Alias of the string form"

NoteBlock
    This whole block is ignored by the parser.
End
```

EPL accepts four comment forms:

- `Note: text` — line comment (colon form)
- `Note "text"` — string form, commonly used as a module header or docstring at the top of a file
- `Comment "text"` — alias of the string form
- `NoteBlock ... End` — block comment

Use `Note:`, `Note "..."`, and `NoteBlock` in documentation and production examples. Do not document `#` as a supported comment form unless your target runtime has a test for it.

### 2.3 Identifiers

Identifiers start with a letter or underscore and may contain letters, digits, and underscores.

```text
[A-Za-z_][A-Za-z0-9_]*
```

Recommended style:

- variables and functions: `snake_case`
- classes and interfaces: `PascalCase`
- constants: `UPPER_SNAKE_CASE`

Some reserved words are soft keywords and may also be used as function, parameter, or member names: `match`, `fetch`, `delete`, `where`, and `port`. This is what allows stdlib APIs such as `regex.match`, `net.fetch`, `sql.delete`, and `sql ... where` to parse.

### 2.4 Literals

| Type | Examples | Notes |
| --- | --- | --- |
| Integer | `42`, `-7`, `0` | Whole numbers |
| Decimal | `3.14`, `-0.5`, `1.0` | Floating-point values |
| Text | `"hello"`, `"it's EPL"`, `""` | Use double quotes |
| Boolean | `True`, `False` | `yes`/`no` also tokenize as booleans, but prefer `True`/`False` |
| Nothing | `Nothing` | Null-like value |
| List | `[1, 2, 3]`, `["a", "b"]`, `[]` | Ordered collection |
| Map | `Map with name = "Alice" and age = 30` | Key-value dictionary |

### 2.5 Strings And Interpolation

Strings support variable interpolation with `$name` and expression interpolation with `${...}`.

```epl
name = "World"
Say "Hello, $name!"
Say "2 + 2 = ${2 + 2}"
```

Use interpolation for simple output. For complex expressions, assign the expression to a variable first.

---

## 3. Statements

Statements are line-oriented. Blocks end with `End` or a specific end token such as `EndFunction`, `EndIf`, `EndFor`, or `EndRepeat` where supported.

### 3.1 Variables

Preferred concise form:

```epl
name = "Alice"
age = 25
items = [1, 2, 3]
settings = Map with host = "localhost" and port = 8080
```

English declaration form:

```epl
Create name equal to "Alice"
Create age = 25
Create text title equal to "Report"
Create list scores equal to [10, 20, 30]
```

Compatibility alias:

```epl
Remember name as "Alice"
```

### 3.2 Assignment

```epl
name = "Bob"
Set age to 30
Increase age by 1
Decrease age by 1
```

Use normal reassignment for multiply, divide, and modulo:

```epl
total = total * 2
remaining = remaining % 10
```

### 3.3 Constants

```epl
Constant PI = 3.14159
Constant APP_NAME = "Billing API"
```

Constants cannot be reassigned after initialization.

### 3.4 Output

```epl
Print "Hello"
Say "Hello"
Display "Hello"
Show "Hello"
```

### 3.5 Input

```epl
Input username with prompt "Username: "
Ask "Password: " store in password
Ask "Email: " and store in email
```

---

## 4. Expressions

### 4.1 Arithmetic

| Syntax | Meaning |
| --- | --- |
| `a + b` | Addition or text concatenation |
| `a - b` | Subtraction |
| `a * b` | Multiplication |
| `a / b` | Division |
| `a % b` | Modulo |
| `power(a, b)` | Exponentiation |
| `a raised to b` | English exponentiation form |

### 4.2 Comparison

| Syntax | Meaning |
| --- | --- |
| `a == b`, `a is equal to b`, `a equals b` | Equality |
| `a != b`, `a is not equal to b`, `a does not equal b` | Inequality |
| `a > b`, `a is greater than b` | Greater than |
| `a < b`, `a is less than b` | Less than |
| `a >= b`, `a is at least b` | Greater than or equal |
| `a <= b`, `a is at most b` | Less than or equal |

### 4.3 Logical Operators

```epl
If is_active And score > 80 Then
    Say "eligible"
End

If Not is_locked Then
    Say "open"
End
```

`And`, `Or`, and `Not` are the recommended spellings in docs, though lower-case forms tokenize too.

### 4.4 Ternary Expression

```epl
age_group = "adult" if age >= 18 otherwise "minor"
```

---

## 5. Collections

### 5.1 Lists

```epl
items = [3, 1, 4]
items.add(1)
first = items[0]
items.sort()
items.reverse()
joined = items.join(", ")
```

Common list methods:

| Method | Purpose |
| --- | --- |
| `add(item)` | Append item |
| `remove(item)` | Remove first matching value |
| `contains(item)` | Membership test |
| `sort()` | Sort in place |
| `reverse()` | Reverse in place |
| `join(separator)` | Join elements as text |
| `pop()` | Remove and return the last item |
| `clear()` | Empty the list |
| `map(fn)`, `filter(fn)`, `reduce(fn)` | Functional transforms |
| `find(fn)`, `every(fn)`, `some(fn)` | Functional predicates |
| `slice(start, end)` | Return a slice |
| `unique()`, `flatten()`, `sum()`, `min()`, `max()` | Convenience helpers |

### 5.2 Maps

Current map literal syntax:

```epl
person = Map with name = "Alice" and age = 30
Say person.name
person.set("role", "admin")
Say person.get("role", "user")
```

Map keys in literals are identifiers. For dynamic keys, build the map and call `set`.

```epl
headers = Map with content_type = "application/json"
headers.set("X-Request-ID", request_id)
```

`Map with ... and ...` literals may be written on a single logical line, or spread across multiple lines by breaking around each `and` separator:

```epl
Create config equal to Map with host = "localhost"
    and port = 8080
    and debug = True
Say config.get("port")
```

Each continuation line begins with `and key = value`. Single-line maps still terminate correctly. For maps with dynamic keys, build the map and call `.set()`.

Common map methods:

| Method | Purpose |
| --- | --- |
| `keys()` | List keys |
| `values()` | List values |
| `entries()` | List key-value pairs |
| `has(key)` | Check for key |
| `get(key, default)` | Read key with default |
| `set(key, value)` | Set key |
| `remove(key)` | Delete key |
| `merge(other)` | Merge maps |
| `clear()` | Empty map |
| `copy()` | Copy map |

---

## 6. Control Flow

### 6.1 If / Otherwise

```epl
If age >= 18 Then
    Say "Adult"
Otherwise If age >= 13 Then
    Say "Teen"
Otherwise
    Say "Child"
End
```

### 6.2 Match / When

```epl
Match grade
    When "A"
        Say "Excellent"
    When "B" or "C"
        Say "Good"
    Default
        Say "Unknown"
End
```

### 6.3 While

```epl
counter = 0
While counter < 10
    Say counter
    Increase counter by 1
End
```

### 6.4 Repeat

```epl
Repeat 5 times
    Say "Hello"
End
```

### 6.5 For Range

```epl
For i from 1 to 10
    Say i
End

For i from 0 to 20 step 2
    Say i
End
```

### 6.6 For Each

```epl
names = ["Alice", "Bob", "Charlie"]
For Each name In names
    Say "Hello, $name"
End
```

### 6.7 Break And Continue

```epl
For i from 1 to 100
    If i == 50 Then
        Break
    End
    If i % 2 == 0 Then
        Continue
    End
    Say i
End
```

---

## 7. Functions And Lambdas

### 7.1 Function Definitions

```epl
Function greet takes name
    Say "Hello, $name"
End

Function add takes a, b
    Return a + b
End

Function factorial takes n
    If n <= 1 Then
        Return 1
    End
    Return n * factorial(n - 1)
End
```

Long English form:

```epl
Define a function named double that takes x
    Return x * 2
End
```

### 7.2 Parameters

Parameters may be separated with commas or `and`.

```epl
Function add takes a, b
    Return a + b
End

Function multiply takes a and b
    Return a * b
End
```

Default parameters and rest parameters are supported by the parser for supported runtimes:

```epl
Function greet takes name = "friend"
    Say "Hello, $name"
End

Function total takes rest numbers
    Return numbers.sum()
End
```

### 7.3 Lambdas

```epl
double = lambda x -> x * 2
add = lambda a, b -> a + b

nums = [1, 2, 3]
Say nums.map(lambda x -> x * 2)
```

`given x return expression` is also parsed as a lambda-style expression. Prefer `lambda ... -> ...` in public docs.

---

## 8. Classes And Objects

### 8.1 Basic Class

```epl
Class Animal
    name = "Unknown"
    sound = "..."

    Function speak
        Say name + " says " + sound
    End
End

dog = new Animal
dog.name = "Rex"
dog.sound = "Woof"
dog.speak()
```

### 8.2 Constructor Pattern

`init` is the constructor called when arguments are provided.

```epl
Class Counter
    value = 0

    Function init takes start
        value = start
    End

    Function increment
        Increase value by 1
        Return value
    End
End

counter = new Counter(10)
Say counter.increment()
```

### 8.3 Inheritance

```epl
Class Dog extends Animal
    Function init takes dog_name
        name = dog_name
        sound = "Woof"
    End
End
```

Interfaces, visibility keywords, static methods, generic classes, and `Super` are implemented surfaces, but they should be covered by project-specific tests before use in production libraries.

---

## 9. Modules And Imports

### 9.1 Module Blocks

```epl
Module Utils
    Constant VERSION = "1.0"

    Function double takes x
        Return x * 2
    End
End

Say Utils::VERSION
Say Utils::double(5)
```

### 9.2 File And Standard Library Imports

```epl
Import "helpers.epl"
Import "math" as Math
Use "collections" as Collections
```

Import resolution checks:

1. Exact path
2. Path plus `.epl`
3. Relative to current file
4. Built-in EPL standard library under `epl/stdlib/`
5. Installed packages such as `epl_modules/` and user package cache

Bundled stdlib modules import in two ways:

```epl
Note: Bare import brings function names into the current scope.
Import "encoding"
Say to_base64("hi")

Note: Aliased import namespaces them under the alias.
Import "encoding" as ENC
Say ENC.to_base64("hi")
```

The shippable importable modules are `json`, `encoding`, `net`, `os`, `regex`, and `sql`. See `docs/stdlib-reference.md` for their public APIs. Because `json` is a reserved token, member access such as `json.parse(...)` will not lex; use the bare form (`Import "json"` then `parse(...)`) or, preferably, an alias (`Import "json" as J` then `J.stringify(...)`).

### 9.3 Python Bridge

```epl
Note: `json` is a reserved token, so alias the Python module to a non-reserved name.
Use python "json" as pyjson

payload = pyjson.loads("{\"ok\": true}")
Say payload.get("ok")
```

Third-party dependencies belong in `epl.toml`:

```toml
[python-dependencies]
requests = "*"
yaml = "pyyaml>=6"
```

Sandbox mode blocks `Use python`.

### 9.4 JavaScript And TypeScript Bridge

```epl
Use javascript "lodash" as lodash
Use typescript "axios" as axios

Say lodash.capitalize("hello from epl")
```

Manage JS dependencies with:

```bash
epl jsinstall lodash
epl jsremove lodash
epl jsdeps
```

Sandbox mode blocks `Use javascript` and `Use typescript`.

---

## 10. Error Handling

```epl
Try
    result = risky_operation()
    Say result
Catch error
    Say "Error: $error"
Finally
    Say "cleanup"
End
```

Throw errors with:

```epl
Throw "Invalid input"
```

Some older examples use `Raise`; prefer `Throw` in current docs.

Assertions:

```epl
Assert length(items) > 0
Assert name != Nothing
```

---

## 11. Native WebApp Syntax

The served web runtime is the native `Create WebApp` DSL.

```epl
Create WebApp called app

Route "/" shows
    Page "Welcome"
        Heading "Welcome to EPL"
        Text "Server-rendered page route"
        Link "Users API" to "/api/users"
    End
End

Route "/api/users" responds with
    users = ["Alice", "Bob"]
    Send json Map with users = users and count = length(users)
End

Start app on port 8000
```

When using `epl serve app.epl`, the CLI can host the app without an explicit `Start app on port ...` in many project workflows. Keep `Start app on port ...` in standalone examples that are run directly.

### 11.1 Request Context

Inside route bodies:

| Name | Meaning |
| --- | --- |
| `request_data` | Parsed request body as map |
| `request_params` | Path and query parameters |
| `request_headers` | Request headers |
| `request_method` | HTTP method |
| `request_path` | Normalized request path |
| `request` | Combined request object |
| `session_id` | Current session identifier when present |

```epl
Route "/users/:name" responds with
    name = request_params.name
    role = request_data.get("role", "guest")
    Send json Map with name = name and role = role and method = request_method
End
```

### 11.2 Page Elements

Common page elements:

```epl
Page "Dashboard"
    Heading "Dashboard"
    Subheading "Today"
    Text "Status: $status"
    Link "Home" to "/"
    Button "Refresh"
    Div class "panel"
        Text "Nested content"
    End
End
```

Use `Raw HTML` only for trusted static markup:

```epl
Page "Trusted Markup"
    Raw HTML "<strong>Trusted markup only</strong>"
End
```

Never pass user-controlled input into `Raw HTML`.

---

## 12. Database Syntax

### 12.1 Built-in SQLite

Use `db_*` for the primary SQLite path:

```epl
db = db_open("app.db")
db_execute(db, "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE)")
db_execute(db, "INSERT INTO users (name, email) VALUES (?, ?)", ["Alice", "alice@example.com"])
users = db_query(db, "SELECT id, name, email FROM users ORDER BY id")
db_close(db)
```

Production guidance:

- Use raw `CREATE TABLE` SQL through `db_execute` for migrations.
- Use parameter placeholders for all external values.
- `db_create_table` now accepts standard SQL column constraints and parameterized types in its column map, for example `INTEGER PRIMARY KEY`, `TEXT NOT NULL`, `VARCHAR(255)`, and `DECIMAL(10,2)`. Allowed type words include `DECIMAL`, `FLOAT`, `DOUBLE`, `CHAR`, and `TIMESTAMP`. Identifiers are still validated and SQL injection is still blocked.
- Close connections in long-running scripts and tests.

### 12.2 Additional Adapters

`real_db_*` helpers support integration with PostgreSQL, MySQL, and SQLite when drivers and URLs are available:

```epl
db = real_db_connect("sqlite:///app.db")
rows = real_db_query(db, "SELECT * FROM users WHERE active = ?", [True])
real_db_close(db)
```

Validate non-SQLite deployments in your own environment.

---

## 13. Standard Library Surface

Built-ins available without imports include:

- Core conversion: `length`, `type_of`, `to_integer`, `to_decimal`, `to_text`, `to_boolean`
- Math: `sqrt`, `power`, `floor`, `ceil`, `round`, `absolute`, `random(min, max)`, `min`, `max`
- String and collection helpers: `uppercase`, `lowercase`, `trim`, `split`, `join`, `contains`, `keys`, `values`
- File and directory helpers: `file_read`, `file_write`, `file_exists`, `dir_list`, `path_join`
- HTTP and JSON: `http_get`, `http_post`, `json_parse`, `json_stringify`
- Database: `db_open`, `db_execute`, `db_query`, `db_query_one`, `db_insert`, `db_close`
- Auth: `auth_hash_password`, `auth_verify_password`, `auth_jwt_create`, `auth_jwt_verify`
- WebSocket: `ws_server_create`, `ws_on_connect`, `ws_on_message`, `ws_broadcast`
- Templates: `template_render`, `template_render_string`

In addition to the always-available built-ins, six bundled modules under `epl/stdlib/` are importable: `json`, `encoding`, `net`, `os`, `regex`, and `sql`. These are thin EPL wrappers over the Python-backed built-ins (`json_parse`, `regex_match`, `db_*`, and so on), which remain callable directly without an import. Import them bare to bring functions in as plain names, or with `as` to namespace them.

See `docs/stdlib-reference.md` for the current reference and optional dependency notes.

---

## 14. CLI Reference

```bash
epl <file.epl>
epl run <file.epl>
epl run
epl new <name> --template web
epl build <file.epl>
epl test
epl repl
epl serve <file.epl> --port 8080
epl js <file.epl>
epl node <file.epl>
epl python <file.epl>
epl kotlin <file.epl>
epl android <file.epl>
epl ios <file.epl>
epl desktop <file.epl>
epl web <file.epl>
epl vm <file.epl>
epl debug <file.epl>
epl fmt <file-or-dir>
epl lint
epl check
epl install <package>
epl pyinstall <import> [spec]
epl jsinstall <package> [version]
epl gitinstall <owner/repo>
epl deploy k8s <file.epl> --image app:1.0 --host app.example.com --tls
epl playground
epl --version
```

Flags commonly used in production checks:

| Flag | Effect |
| --- | --- |
| `--strict` | Enable static checking where supported |
| `--sandbox` | Disable dangerous built-ins and ecosystem bridges |
| `--verbose` | Show diagnostic output |
| `--quiet` | Suppress non-error output |
| `--no-color` | Disable ANSI color |

---

## 15. Current Grammar Summary

This is a practical summary, not a byte-for-byte copy of the parser.

```ebnf
program        = { statement newline } ;

statement      = var_decl | assignment | print_stmt | input_stmt
               | if_stmt | match_stmt | while_stmt | repeat_stmt
               | for_range | for_each | function_def | class_def
               | module_def | import_stmt | use_stmt | try_stmt
               | return_stmt | throw_stmt | assert_stmt
               | webapp_stmt | route_stmt | start_stmt
               | expression_stmt ;

var_decl       = identifier "=" expression
               | "Create" [ type ] identifier ( "equal" [ "to" ] | "=" | "as" ) expression
               | "Remember" identifier "as" expression ;

assignment     = identifier "=" expression
               | "Set" identifier "to" expression
               | ( "Increase" | "Decrease" ) identifier "by" expression ;

print_stmt     = ( "Print" | "Say" | "Display" | "Show" ) expression ;
input_stmt     = "Input" identifier [ "with" "prompt" string ]
               | "Ask" [ string ] [ "and" ] [ "store" ] [ "in" ] identifier ;

if_stmt        = "If" expression [ "Then" ] block
                 { "Otherwise" "If" expression [ "Then" ] block }
                 [ "Otherwise" block ] "End" ;

match_stmt     = "Match" expression { "When" expression block } [ "Default" block ] "End" ;
while_stmt     = "While" expression block "End" ;
repeat_stmt    = "Repeat" expression "times" block "End" ;
for_range      = "For" identifier "from" expression "to" expression [ "step" expression ] block "End" ;
for_each       = "For" "Each" identifier "In" expression block "End" ;

function_def   = "Function" identifier [ "takes" param_list ] block "End"
               | "Define" [ "a" ] "function" [ "named" ] identifier [ "that" "takes" param_list ] block "End" ;

class_def      = "Class" identifier [ "extends" identifier ] class_body "End" ;
module_def     = "Module" identifier block "End" ;
import_stmt    = "Import" string [ "as" identifier ] ;
use_stmt       = "Use" string [ "as" identifier ]
               | "Use" "python" string [ "as" identifier ]
               | "Use" ( "javascript" | "typescript" ) string [ "as" identifier ] ;

try_stmt       = "Try" block "Catch" identifier block [ "Finally" block ] "End" ;
return_stmt    = "Return" [ expression ] ;
throw_stmt     = "Throw" expression ;
assert_stmt    = "Assert" expression ;

webapp_stmt    = "Create" "WebApp" [ "called" ] identifier ;
route_stmt     = "Route" string ( "shows" | "responds" [ "with" ] ) block "End" ;
start_stmt     = "Start" identifier [ "on" ] [ "port" ] expression ;

expression     = ternary ;
ternary        = or_expr [ "if" expression "otherwise" expression ] ;
or_expr        = and_expr { "or" and_expr } ;
and_expr       = not_expr { "and" not_expr } ;
not_expr       = [ "not" ] comparison ;
comparison     = addition { comparison_operator addition } ;
addition       = multiplication { ( "+" | "-" ) multiplication } ;
multiplication = unary { ( "*" | "/" | "%" ) unary } ;
unary          = [ "-" | "not" ] postfix ;
postfix        = primary { call | index | slice | property | method_call } ;
primary        = number | string | "True" | "False" | "Nothing"
               | identifier | list_literal | map_literal | lambda_expr
               | "new" identifier [ call_args ] | "(" expression ")" ;

list_literal   = "[" [ expression { "," expression } ] "]" ;
map_literal    = "Map" "with" identifier "=" expression { [ newline ] "and" identifier "=" expression } ;
lambda_expr    = "lambda" param_list "->" expression ;
```

---

## 16. Enterprise Production Checklist

- Pin EPL and dependency versions in CI.
- Run parser smoke tests for every documented example your product depends on.
- Use `db_execute` migrations for real schemas and parameterized queries for all external values.
- Run web apps behind a reviewed production server and trusted proxy configuration.
- Keep secrets in environment variables or a secret manager, never in EPL source.
- Enable `--sandbox` for untrusted code.
- Treat Python/JS bridges as privileged integration points.
- Validate deployment artifacts against your own cluster/cloud policy before rollout.

---

*EPL v9.8.0 - Write readable programs in plain English, with clear production boundaries.*
