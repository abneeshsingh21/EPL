# EPL Language Reference

Complete reference for EPL v9.8.0 syntax that is stable enough to teach in user-facing documentation.

## Table Of Contents

1. [Comments](#comments)
2. [Variables](#variables)
3. [Data Types](#data-types)
4. [Operators](#operators)
5. [Control Flow](#control-flow)
6. [Functions](#functions)
7. [Classes](#classes)
8. [Collections](#collections)
9. [Error Handling](#error-handling)
10. [Modules And Bridges](#modules-and-bridges)
11. [WebApp DSL](#webapp-dsl)
12. [Built-in Functions](#built-in-functions)
13. [Methods](#methods)
14. [Production Boundaries](#production-boundaries)

---

## Comments

```epl
Note: line comment using the colon form

Note "string-form comment, handy as a file header or docstring"
Comment "alias of the string form"

NoteBlock
    A block comment spanning
    multiple lines.
End
```

EPL accepts four comment forms: `Note: text`, `Note "text"`, `Comment "text"`, and the `NoteBlock ... End` block.

---

## Variables

```epl
name = "Alice"
age = 25
active = True
score = 99.5
items = [1, 2, 3]
profile = Map with name = "Alice" and age = 25
```

English declaration forms:

```epl
Create name equal to "Alice"
Create age = 25
Create text title equal to "Invoice"
Remember city as "Delhi"
```

Assignment:

```epl
name = "Bob"
Set age to 30
Increase age by 1
Decrease age by 1
```

Constants:

```epl
Constant MAX_RETRIES = 3
Constant APP_NAME = "Orders API"
```

---

## Data Types

| Type | Example | Recommended Literal |
| --- | --- | --- |
| Integer | `42` | `42` |
| Decimal | `3.14` | `3.14` |
| Text | `"Hello"` | double-quoted text |
| Boolean | `True`, `False` | capitalized |
| List | `[1, 2, 3]` | square brackets |
| Map | `Map with id = 1 and name = "A"` | `Map with ... and ...` |
| Nothing | `Nothing` | capitalized |

Type helpers:

```epl
Say type_of(42)
Say is_integer(42)
Say is_text("hello")
Say is_list([1, 2])
Say is_number(3.14)
Say is_nothing(Nothing)
```

Conversions:

```epl
count = to_integer("42")
price = to_decimal("19.95")
value_text = to_text(42)
flag = to_boolean(1)
```

---

## Operators

Arithmetic:

| Operator | Example |
| --- | --- |
| `+` | `total = a + b` |
| `-` | `remaining = total - used` |
| `*` | `area = width * height` |
| `/` | `ratio = done / total` |
| `%` | `remainder = n % 2` |
| `power(a, b)` | `value = power(2, 10)` |
| `raised to` | `value = 2 raised to 10` |

Comparison:

| Operator | English Form |
| --- | --- |
| `==` | `is equal to`, `equals` |
| `!=` | `is not equal to`, `does not equal` |
| `>` | `is greater than` |
| `<` | `is less than` |
| `>=` | `is at least` |
| `<=` | `is at most` |

Logical:

```epl
If enabled And count > 0 Then
    Say "run"
End

If Not locked Or owner == "admin" Then
    Say "allowed"
End
```

Ternary:

```epl
age_group = "adult" if age >= 18 otherwise "minor"
```

---

## Control Flow

If / Otherwise:

```epl
If age >= 18 Then
    Say "Adult"
Otherwise If age >= 13 Then
    Say "Teen"
Otherwise
    Say "Child"
End
```

Match:

```epl
Match status
    When "new"
        Say "Create"
    When "paid"
        Say "Ship"
    Default
        Say "Review"
End
```

While:

```epl
i = 0
While i < 10
    Say i
    Increase i by 1
End
```

Repeat:

```epl
Repeat 3 times
    Say "retry"
End
```

For range:

```epl
For i from 1 to 10
    Say i
End

For i from 0 to 20 step 2
    Say i
End
```

For each:

```epl
names = ["Alice", "Bob"]
For Each name In names
    Say "Hello, $name"
End
```

Break and continue:

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

## Functions

Definition:

```epl
Function greet takes name
    Say "Hello, $name"
End

Function add takes a, b
    Return a + b
End
```

Call:

```epl
greet("Alice")
result = add(3, 4)
```

Parameters can be comma-separated or joined with `and`:

```epl
Function multiply takes a and b
    Return a * b
End
```

Lambdas:

```epl
square = lambda x -> x * x
add = lambda a, b -> a + b

numbers = [1, 2, 3, 4]
Say numbers.map(lambda x -> x * 2)
```

Input:

```epl
Ask "Name: " store in name
Input email with prompt "Email: "
```

---

## Classes

Basic class:

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

Constructor:

```epl
Class Counter
    value = 0

    Function init takes start
        value = start
    End

    Function next
        Increase value by 1
        Return value
    End
End

counter = new Counter(10)
Say counter.next()
```

Inheritance:

```epl
Class Dog extends Animal
    Function init takes dog_name
        name = dog_name
        sound = "Woof"
    End
End
```

Use project tests before depending on advanced OOP features such as visibility, interfaces, generics, or static methods across all compilation targets.

---

## Collections

Lists:

```epl
items = [3, 1, 4, 1, 5]
items.add(9)
items.remove(1)
Say items.contains(4)
Say items.index_of(4)
Say items.count(1)
items.sort()
items.reverse()
Say items.join(", ")
last = items.pop()
```

Functional list methods:

```epl
nums = [1, 2, 3, 4, 5]
Say nums.map(lambda x -> x * 2)
Say nums.filter(lambda x -> x > 3)
Say nums.reduce(lambda a, b -> a + b)
Say nums.find(lambda x -> x > 3)
Say nums.every(lambda x -> x > 0)
Say nums.some(lambda x -> x > 4)
```

Maps:

```epl
person = Map with name = "Alice" and age = 30
Say person.name
person.set("role", "admin")
Say person.get("role", "user")
Say person.has("name")
Say person.keys()
Say person.values()
person.remove("role")
```

Map literals on one line or across multiple lines:

```epl
Note: Single-line form.
settings = Map with host = "localhost" and port = 8080

Note: Multi-line form breaks around each `and`.
config = Map with host = "localhost"
    and port = 8080
    and debug = True

Note: For dynamic keys, build incrementally with .set().
headers = Map with content_type = "application/json"
headers.set("X-Request-ID", request_id)
```

---

## Error Handling

```epl
Try
    result = 10 / divisor
    Say result
Catch error
    Say "Error: $error"
Finally
    Say "done"
End
```

Throw:

```epl
Function validate_age takes age
    If age < 0 Then
        Throw "Age cannot be negative"
    End
    Return age
End
```

Assert:

```epl
Assert 2 + 2 == 4
Assert length("hello") == 5
```

---

## Modules And Bridges

File and stdlib imports:

```epl
Import "utils.epl"
Import "math" as Math
Use "collections" as Collections
```

Bundled importable modules:

EPL ships six importable modules under `epl/stdlib/`: `json`, `encoding`, `net`, `os`, `regex`, and `sql`. A bare import brings their functions in as plain names; an aliased import namespaces them.

```epl
Note: Bare import — functions become plain names.
Import "encoding"
Say to_base64("hi")

Note: Aliased import — functions are namespaced.
Import "encoding" as ENC
Say ENC.to_base64("hi")
```

`json` is a reserved token, so `json.parse(...)` will not lex. Use the bare form or an alias:

```epl
Import "json" as J
Say J.stringify(Map with a = 1 and b = 2)
```

These modules wrap the always-available built-ins (`json_parse`, `regex_match`, `db_*`, and others), which remain callable directly. See `docs/stdlib-reference.md` for the full per-module API.

Module block:

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

Python bridge:

```epl
Note: `json` is a reserved token, so alias the Python module to a non-reserved name.
Use python "json" as pyjson
payload = pyjson.loads("{\"ok\": true}")
Say payload.get("ok")
```

JavaScript bridge:

```epl
Use javascript "lodash" as lodash
Say lodash.capitalize("hello")
```

Bridge code is privileged. Sandbox mode blocks ecosystem bridges.

---

## WebApp DSL

```epl
Create WebApp called app

Route "/" shows
    Page "Home"
        Heading "Home"
        Text "Welcome"
        Link "Health" to "/api/health"
    End
End

Route "/api/health" responds with
    Send json Map with status = "ok"
End

Start app on port 8000
```

Request context inside route bodies:

| Name | Purpose |
| --- | --- |
| `request_data` | Parsed JSON or form body |
| `request_params` | Path and query params |
| `request_headers` | Headers map |
| `request_method` | HTTP method |
| `request_path` | Request path |
| `request` | Combined request object |
| `session_id` | Session identifier |

```epl
Route "/users/:name" responds with
    name = request_params.name
    role = request_data.get("role", "guest")
    Send json Map with name = name and role = role
End
```

---

## Built-in Functions

Core:

| Function | Purpose |
| --- | --- |
| `length(x)` | Length of text, list, or map |
| `type_of(x)` | Runtime type name |
| `to_integer(x)` | Convert to integer |
| `to_decimal(x)` | Convert to decimal |
| `to_text(x)` | Convert to text |
| `to_boolean(x)` | Convert to boolean |

Math:

| Function | Purpose |
| --- | --- |
| `absolute(x)` | Absolute value |
| `round(x)` | Round number |
| `floor(x)` | Round down |
| `ceil(x)` | Round up |
| `sqrt(x)` | Square root |
| `power(x, y)` | Exponentiation |
| `log(x)` | Natural log |
| `sin(x)`, `cos(x)`, `tan(x)` | Trigonometry |
| `min(a, b)`, `max(a, b)` | Minimum / maximum |
| `random(min, max)` | Random value in range |

Text:

| Function | Purpose |
| --- | --- |
| `uppercase(s)` | Uppercase |
| `lowercase(s)` | Lowercase |
| `trim(s)` | Trim whitespace |
| `split(s, sep)` | Split text |
| `join(list, sep)` | Join list |
| `replace(s, old, new)` | Replace text |

JSON:

| Function | Purpose |
| --- | --- |
| `json_parse(text)` | Parse JSON |
| `json_stringify(value)` | Serialize JSON |
| `json_valid(text)` | Validate JSON where available |
| `json_merge(a, b)` | Merge JSON-like maps where available |
| `json_query(value, path)` | Query JSON-like data where available |

Database:

| Function | Purpose |
| --- | --- |
| `db_open(path)` | Open SQLite |
| `db_execute(db, sql[, params])` | Run SQL statement |
| `db_query(db, sql[, params])` | Query all rows |
| `db_query_one(db, sql[, params])` | Query one row |
| `db_insert(db, table, map)` | Insert map record |
| `db_close(db)` | Close connection |

Auth:

| Function | Purpose |
| --- | --- |
| `auth_hash_password(password)` | Hash password |
| `auth_verify_password(password, hash)` | Verify password |
| `auth_jwt_create(payload, secret[, expiry_seconds])` | Create JWT |
| `auth_jwt_verify(token, secret)` | Verify JWT |
| `auth_generate_token(length)` | Generate random token |

---

## Methods

String methods:

```epl
s = "Hello World"
Say s.uppercase()
Say s.lowercase()
Say s.trim()
Say s.contains("World")
Say s.starts_with("Hello")
Say s.ends_with("World")
Say s.replace("World", "EPL")
Say s.split(" ")
Say s.substring(0, 5)
Say s.index_of("World")
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

List methods:

```epl
items.add("x")
items.remove("x")
items.contains("x")
items.sort()
items.reverse()
items.join(", ")
items.pop()
items.clear()
items.copy()
```

Map methods:

```epl
m.keys()
m.values()
m.entries()
m.has("key")
m.get("key", "default")
m.set("key", "value")
m.remove("key")
m.merge(other)
m.clear()
m.copy()
```

---

## Production Boundaries

- Use `Note:`, `Note "..."`, or `NoteBlock` comments in production documentation.
- Write `Map with ... and ...` on one line or across multiple lines (breaking around each `and`); build maps with dynamic keys incrementally with `.set`.
- Use `db_execute` for production migrations instead of complex `db_create_table` definitions.
- Use parameterized SQL for every value that came from users, files, requests, or external services.
- Use `Send json` in WebApp routes instead of returning bare maps.
- Wrap Python/JS bridge calls in `Try`/`Catch` and declare dependencies in `epl.toml`.
- Run `epl test`, parser smoke tests, and deployment smoke tests for the target you actually ship.
