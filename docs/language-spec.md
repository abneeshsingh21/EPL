# EPL Language Specification v7.0

> **EPL** — English Programming Language  
> A production-ready programming language with plain-English syntax.

---

## 1. Overview

EPL is a general-purpose programming language designed to read like English. Every statement, keyword, and construct uses familiar English words instead of cryptic symbols. EPL supports:

- Variables, constants, and type conversions
- Functions with closures and recursion
- Classes with inheritance and polymorphism
- Modules and namespaces
- Pattern matching (Match/When)
- Error handling (Try/Catch/Finally)
- Collections: lists, dictionaries, sets
- File I/O, networking, databases
- Web framework with routing, templates, WebSocket
- Concurrency (threads, channels, locks)
- LLVM compilation to native code
- Transpilation to JavaScript, Node.js, Kotlin
- Bytecode VM execution
- Standard library (9 native EPL modules + 300+ built-in functions)

---

## 2. Lexical Structure

### 2.1 Comments

```epl
Note: This is a single-line comment
Note: Everything after "Note:" on a line is ignored
```

### 2.2 Identifiers

Identifiers start with a letter or underscore and may contain letters, digits, and underscores.

```
[a-zA-Z_][a-zA-Z0-9_]*
```

### 2.3 Literals

| Type | Examples |
|------|----------|
| Integer | `42`, `-7`, `0` |
| Decimal | `3.14`, `-0.5`, `1.0` |
| Text (String) | `"hello"`, `"it's EPL"`, `""` |
| Boolean | `True`, `False` |
| Nothing | `Nothing` |
| List | `[1, 2, 3]`, `["a", "b"]`, `[]` |
| Dictionary | `{"key": "value", "age": 25}` |

### 2.4 String Templates

Strings support `$variable` and `${expression}` interpolation:

```epl
Create name equal to "World"
Say "Hello, $name!"              Note: Hello, World!
Say "2 + 2 = ${2 + 2}"          Note: 2 + 2 = 4
```

### 2.5 Keywords (Reserved Words)

```
Create Set If Then Else End While For Each In
Define Function Takes Return EndFunction
Class Inherits Constructor Method EndClass
Module EndModule Import Use As
Try Catch Finally EndTry Throw
Match When Default EndMatch
Print Say Ask Input Display Show
And Or Not Is True False Nothing
Constant Assert Exit Wait
To From Step By
Break Continue
Repeat Times EndRepeat
Async Await
New Self Super
Equal Greater Less Than At Most Least
```

---

## 3. Statements

### 3.1 Line Termination

Statements are line-terminated. One statement per line (no semicolons required).

### 3.2 Variable Declaration

```epl
Create x equal to 10
Create name equal to "Alice"
Create items equal to [1, 2, 3]
Create config equal to {"port": 8080, "debug": True}
```

English alias:
```epl
Remember x as 10
```

### 3.3 Variable Assignment

```epl
Set x to 20
Set name to "Bob"
```

Compound assignment:
```epl
Set x to x + 1      Note: standard
Set x += 1           Note: shorthand increment
Set x -= 5           Note: shorthand decrement
Set x *= 2           Note: shorthand multiply
Set x /= 4           Note: shorthand divide
Set x %= 3           Note: shorthand modulo
```

### 3.4 Constants

```epl
Constant PI = 3.14159
Constant MAX_SIZE = 100
```

Constants cannot be reassigned after initialization.

### 3.5 Print / Output

```epl
Print "Hello"            Note: print with newline
Say "Hello"              Note: English alias for Print
Display items            Note: alias for Print
Show result              Note: alias for Print
```

### 3.6 Input

```epl
Create name equal to Input "What is your name? "
Create age equal to Ask "How old are you? "    Note: alias
```

---

## 4. Expressions

### 4.1 Arithmetic

| Operator | Meaning |
|----------|---------|
| `+` | Addition / String concatenation |
| `-` | Subtraction |
| `*` | Multiplication |
| `/` | Division |
| `%` | Modulo |
| `power(a, b)` | Exponentiation |

### 4.2 Comparison

| Syntax | Meaning |
|--------|---------|
| `==` or `is equal to` | Equality |
| `!=` or `is not equal to` | Inequality |
| `>` or `is greater than` | Greater |
| `<` or `is less than` | Less |
| `>=` or `is at least` | Greater or equal |
| `<=` or `is at most` | Less or equal |

### 4.3 Logical

| Operator | Meaning |
|----------|---------|
| `And` / `and` | Logical AND |
| `Or` / `or` | Logical OR |
| `Not` / `not` | Logical NOT |

### 4.4 String Operations

```epl
Create full equal to first + " " + last     Note: concatenation
Create len equal to length(name)             Note: length
Create sub equal to substring(name, 0, 3)   Note: substring
Create up equal to uppercase(name)           Note: uppercase
Create low equal to lowercase(name)          Note: lowercase
```

### 4.5 List Operations

```epl
Create items equal to [1, 2, 3]
append(items, 4)                    Note: add to end
remove(items, 2)                    Note: remove first occurrence
Create first equal to items[0]      Note: index access
Create len equal to length(items)   Note: list length
Create has equal to contains(items, 3)  Note: membership test
```

### 4.6 Dictionary Operations

```epl
Create config equal to {"host": "localhost", "port": 8080}
Create host equal to config["host"]         Note: access by key
Set config["debug"] to True                 Note: set key
Create ks equal to keys(config)             Note: get all keys
Create vs equal to values(config)           Note: get all values
```

### 4.7 Member Access

```epl
Create len equal to name.length        Note: property access
Create up equal to name.upper()        Note: method call
Module::function_name()                Note: module-scoped access
```

---

## 5. Control Flow

### 5.1 If / Else

```epl
If condition Then
    Note: body
End

If x > 10 Then
    Say "Big"
Else
    Say "Small"
End

If score >= 90 Then
    Say "A"
Else If score >= 80 Then
    Say "B"
Else If score >= 70 Then
    Say "C"
Else
    Say "F"
End
```

### 5.2 Match / When (Pattern Matching)

```epl
Match grade
    When "A"
        Say "Excellent"
    When "B", "C"
        Say "Good"
    When "D"
        Say "Needs work"
    Default
        Say "Unknown"
EndMatch
```

### 5.3 While Loop

```epl
Create counter equal to 0
While counter < 10
    Say counter
    Set counter to counter + 1
End
```

### 5.4 For Loop (Range)

```epl
For i from 1 to 10
    Say i
End

For i from 0 to 20 step 2
    Say i              Note: 0, 2, 4, ..., 20
End
```

### 5.5 For Each Loop

```epl
Create names equal to ["Alice", "Bob", "Charlie"]
For Each name In names
    Say "Hello, $name!"
End
```

### 5.6 Repeat Loop

```epl
Repeat 5 Times
    Say "Hello!"
End
```

### 5.7 Break / Continue

```epl
For i from 1 to 100
    If i == 50 Then
        Break          Note: exit loop
    End
    If i % 2 == 0 Then
        Continue       Note: skip even numbers
    End
    Say i
End
```

---

## 6. Functions

### 6.1 Definition

```epl
Define Function greet Takes name
    Say "Hello, $name!"
EndFunction

Define Function add Takes a, b
    Return a + b
EndFunction

Define Function factorial Takes n
    If n <= 1 Then
        Return 1
    End
    Return n * factorial(n - 1)
EndFunction
```

### 6.2 Calling

```epl
greet("Alice")
Create result equal to add(3, 4)
```

### 6.3 Default Parameters

Functions without required arguments can be called with fewer arguments.

### 6.4 Lambda / Anonymous Functions

```epl
Create double equal to Lambda x: x * 2
Say double(5)          Note: 10
```

---

## 7. Classes & OOP

### 7.1 Class Definition

```epl
Class Animal
    Constructor Takes name, sound
        Set Self.name to name
        Set Self.sound to sound
    EndConstructor

    Method speak
        Say "$Self.name says $Self.sound!"
    EndMethod

    Method get_name
        Return Self.name
    EndMethod
EndClass
```

### 7.2 Instantiation

```epl
Create dog equal to new Animal("Dog", "Woof")
dog.speak()            Note: Dog says Woof!
```

### 7.3 Inheritance

```epl
Class Dog Inherits Animal
    Constructor Takes name
        Super("Dog: " + name, "Woof")
        Set Self.tricks to []
    EndConstructor

    Method learn Takes trick
        append(Self.tricks, trick)
    EndMethod

    Method show_tricks
        Say "$Self.name knows: $Self.tricks"
    EndMethod
EndClass
```

### 7.4 Static Methods

```epl
Class MathUtils
    Method Static add Takes a, b
        Return a + b
    EndMethod
EndClass

Create result equal to MathUtils.add(3, 4)
```

---

## 8. Modules & Imports

### 8.1 Module Definition

```epl
Module Utils
    Define Function helper Takes x
        Return x * 2
    EndFunction

    Constant VERSION = "1.0"
End
```

Access via `Module::member`:
```epl
Create result equal to Utils::helper(5)
Say Utils::VERSION
```

### 8.2 Import (File)

```epl
Import "helpers.epl"           Note: merge all exports into current scope
Import "utils.epl" as Utils    Note: import as namespace (Utils::func)
```

### 8.3 Import (Standard Library)

```epl
Import "math"                  Note: imports EPL stdlib math module
Import "math" as Math          Note: imports as namespace (Math::factorial)
Import "string"                Note: string utilities
Import "collections"           Note: collections, stack, queue
Import "io"                    Note: file and console I/O
Import "testing"               Note: test framework
Import "datetime"              Note: date/time utilities
Import "functional"            Note: map, filter, reduce, compose
Import "http"                  Note: HTTP client
Import "crypto"                Note: hashing, encoding, random
```

### 8.4 Import Resolution Order

1. Exact file path
2. Path + `.epl` extension
3. Relative to current file directory
4. EPL standard library (`epl/stdlib/<name>.epl`)
5. Package manager (`epl_modules/`, `~/.epl/packages/`)

### 8.5 Python Bridge

```epl
Use python "json" as json
Use python "os" as os
Use python "requests" as req
```

For project-managed third-party packages, declare them in `epl.toml`:

```toml
[github-dependencies]
web-kit = "epl-lang/web-kit"

[python-dependencies]
requests = "*"
yaml = "pyyaml>=6"
```

When a bridged module is not installed, EPL can install:
1. project-declared dependencies from `[python-dependencies]`
2. selected allowlisted packages automatically

EPL projects can also declare GitHub-hosted EPL packages in `[github-dependencies]` and install them with `epl install` or `epl gitinstall owner/repo`.

---

## 9. Error Handling

### 9.1 Try / Catch / Finally

```epl
Try
    Create result equal to risky_operation()
    Say result
Catch error
    Say "Error: $error"
Finally
    cleanup()
EndTry
```

### 9.2 Throw

```epl
Throw "Something went wrong"
Throw "Invalid input: $value"
```

### 9.3 Assert

```epl
Assert x > 0
Assert length(items) == 5
Assert name != Nothing
```

---

## 10. Web Framework

### 10.1 Routes

```epl
Route GET "/" handler home_page
Route POST "/api/data" handler process_data
Route GET "/users/:id" handler get_user
```

### 10.2 Handlers

```epl
Define Function home_page Takes request
    Return "<h1>Welcome to EPL!</h1>"
EndFunction

Define Function get_user Takes request
    Create id equal to request["params"]["id"]
    Return json_stringify({"id": id, "name": "User"})
EndFunction
```

### 10.3 Templates

```epl
Template "page" content
    <html>
    <body>
        ${content}
    </body>
    </html>
EndTemplate
```

### 10.4 WebSocket

```epl
WebSocket "/ws" handler ws_handler
```

### 10.5 Middleware

```epl
Middleware auth_check
```

### 10.6 Server

```epl
Serve on port 8080
```

Production server: `epl serve webapp.epl --port 8080 --workers 4`

---

## 11. Standard Library (Native EPL)

EPL ships with 9 native EPL modules in `epl/stdlib/`:

| Module | Description | Key Functions |
|--------|-------------|---------------|
| `math` | Math operations | `factorial`, `fibonacci`, `is_prime`, `gcd`, `lcm`, `average`, `median` |
| `string` | String utilities | `repeat_string`, `pad_left`, `capitalize`, `title_case`, `truncate`, `slug` |
| `collections` | Data structures | `flatten`, `chunk`, `unique`, `stack_*`, `queue_*` |
| `io` | File/console I/O helpers | `read_file`, `write_file`, `file_lines`, `path_join`, `prompt` |
| `testing` | Test framework | `test()`, `expect_equal`, `expect_true`, `expect_contains`, `test_summary` |
| `datetime` | Date/time | `format_duration`, `time_ago`, timer functions |
| `functional` | FP utilities | `map_list`, `filter_list`, `reduce_list`, `compose`, `pipe`, `memoize` |
| `http` | HTTP client helpers | `get`, `post`, `status helpers`, `parse_json`, `to_json` |
| `crypto` | Crypto/encoding | `md5`, `sha256`, `to_base64`, `uuid`, `random_string` |

Plus 300+ built-in functions available without imports (math, string, file, database, networking, etc.).

---

## 12. Built-in Functions

### 12.1 Core

| Function | Description |
|----------|-------------|
| `length(x)` | Length of string, list, or dict |
| `type_of(x)` | Type name as string |
| `to_integer(x)` | Convert to integer |
| `to_text(x)` | Convert to string |
| `to_decimal(x)` | Convert to float |
| `to_boolean(x)` | Convert to boolean |

### 12.2 Math

| Function | Description |
|----------|-------------|
| `sqrt(x)` | Square root |
| `power(x, n)` | Exponentiation |
| `floor(x)` | Floor |
| `ceil(x)` | Ceiling |
| `round(x)` | Round |
| `absolute(x)` | Absolute value |
| `random()` | Random 0..1 |
| `min(a, b)` | Minimum |
| `max(a, b)` | Maximum |
| `log(x)` | Natural log |
| `sin(x)`, `cos(x)`, `tan(x)` | Trigonometry |

### 12.3 Collections

| Function | Description |
|----------|-------------|
| `range(n)` | List [0..n-1] |
| `sum(list)` | Sum of numeric list |
| `sorted(list)` | Sorted copy |
| `reversed(list)` | Reversed copy |
| `keys(dict)` | Dictionary keys |
| `values(dict)` | Dictionary values |
| `append(list, item)` | Add to list |
| `remove(list, item)` | Remove from list |
| `contains(col, item)` | Membership test |
| `join(list, sep)` | Join to string |
| `split(str, sep)` | Split string |
| `index_of(list, item)` | Find index |

### 12.4 I/O

| Function | Description |
|----------|-------------|
| `file_read(path)` | Read file contents |
| `file_write(path, data)` | Write file |
| `file_append(path, data)` | Append to file |
| `file_exists(path)` | Check existence |
| `file_delete(path)` | Delete file |
| `dir_list(path)` | List directory |
| `dir_create(path)` | Create directory |

### 12.5 Networking

| Function | Description |
|----------|-------------|
| `http_get(url)` | HTTP GET |
| `http_post(url, data)` | HTTP POST |
| `json_parse(str)` | Parse JSON |
| `json_stringify(obj)` | Serialize JSON |

---

## 13. Concurrency

### 13.1 Threads

```epl
Create t equal to real_thread_run(my_function, arg1, arg2)
real_thread_join(t)
```

### 13.2 Channels

```epl
Create ch equal to real_channel_create(10)  Note: buffered channel
real_channel_send(ch, "message")
Create msg equal to real_channel_receive(ch)
```

### 13.3 Mutexes

```epl
Create lock equal to real_mutex_create()
real_mutex_lock(lock)
Note: critical section
real_mutex_unlock(lock)
```

### 13.4 Async / Await

```epl
Async Define Function fetch_data Takes url
    Create response equal to Await http_get(url)
    Return response
EndFunction
```

---

## 14. Compilation Targets

### 14.1 Interpreter (Default)

```bash
epl run program.epl
```

### 14.2 LLVM Native Compilation

```bash
epl build program.epl       # Produces program.exe
epl ir program.epl           # Show LLVM IR
```

### 14.3 JavaScript Transpilation

```bash
epl js program.epl           # Produces program.js
```

### 14.4 Node.js Transpilation

```bash
epl node program.epl         # Produces program_node.js
```

### 14.5 Kotlin / Android

```bash
epl kotlin program.epl       # Produces program.kt
epl android program.epl      # Generates Android project
```

### 14.6 Bytecode VM

```bash
epl vm program.epl            # Fast bytecode execution
```

---

## 15. Package Manager

### 15.1 Project Initialization

```bash
epl new myproject             # Create full project structure
epl new myproject --template web
epl new myproject --template api
epl new myproject --template lib
epl init                      # Initialize in current directory
```

### 15.2 Package Management

```bash
epl install <package>         # Install a package
epl uninstall <package>       # Remove a package
epl packages                  # List installed packages
```

### 15.3 Project Structure

```
myproject/
├── epl.toml              # Project manifest
├── README.md
├── .gitignore
├── src/
│   └── main.epl          # Entry point
├── tests/
│   └── test_main.epl     # Tests
├── lib/                  # Local libraries
└── epl_modules/          # Installed packages
```

---

## 16. CLI Reference

```
epl <file.epl>                   Run an EPL program
epl run <file.epl> [flags]       Run with flags
epl run                          Run the current project's manifest entrypoint
epl new <name> [--template T]    Create a new project
epl build <file.epl>             Compile to native executable
epl build                        Build the current project's manifest entrypoint
epl test [dir|file]              Run tests
epl repl                         Interactive REPL
epl install <pkg>                Install package
epl pyinstall <import> [spec]    Install/save a Python package for `Use python`
epl gitinstall <owner/repo>      Install/save a GitHub dependency
epl github <clone|pull|push>     GitHub project workflows
epl serve <file.epl> [opts]      Start production server
epl js <file.epl>                Transpile to JavaScript
epl node <file.epl>              Transpile to Node.js
epl kotlin <file.epl>            Transpile to Kotlin
epl ir <file.epl>                Show LLVM IR
epl vm <file.epl>                Run with bytecode VM
epl debug <file.epl>             Debug with breakpoints
epl fmt <file|dir> [options]     Format source code
epl lint [dir|file]              Lint source code
epl lsp                          Start LSP server
epl ai <prompt>                  AI code assistant
epl --version                    Show version
epl --help                       Show help
```

### 16.1 Flags

| Flag | Effect |
|------|--------|
| `--strict` | Enable static type checking |
| `--sandbox` | Disable dangerous built-ins |
| `--verbose` | Debug output |
| `--quiet` | Suppress non-error output |
| `--no-color` | Disable ANSI colors |

---

## 17. Type System

EPL is dynamically typed with optional static checking (`--strict` mode).

### 17.1 Types

| Type | Description | Example |
|------|-------------|---------|
| `Integer` | Whole numbers | `42` |
| `Decimal` | Floating-point | `3.14` |
| `Text` | Strings | `"hello"` |
| `Boolean` | True/False | `True` |
| `Nothing` | Null/nil | `Nothing` |
| `List` | Ordered collection | `[1, 2, 3]` |
| `Dictionary` | Key-value map | `{"a": 1}` |
| `Function` | Callable | `add` |
| `Class` | Type definition | `Animal` |
| `Object` | Class instance | `new Animal(...)` |

### 17.2 Type Checking Functions

```epl
is_integer(42)       Note: True
is_decimal(3.14)     Note: True
is_text("hello")     Note: True
is_boolean(True)     Note: True
is_list([1, 2])      Note: True
is_map({"a": 1})     Note: True
is_nothing(Nothing)  Note: True
is_number(42)        Note: True (int or float)
type_of(42)          Note: "Integer"
```

---

## 18. Grammar (EBNF Summary)

```ebnf
program        = { statement } ;
statement      = variable_decl | assignment | print_stmt | if_stmt
               | while_stmt | for_stmt | for_each_stmt | repeat_stmt
               | function_def | class_def | module_def | import_stmt
               | use_stmt | try_stmt | match_stmt | return_stmt
               | throw_stmt | assert_stmt | break_stmt | continue_stmt
               | wait_stmt | exit_stmt | route_stmt | expression_stmt ;

variable_decl  = "Create" IDENT "equal to" expression ;
assignment     = "Set" target "to" expression ;
print_stmt     = ("Print" | "Say" | "Display" | "Show") expression ;
if_stmt        = "If" expression "Then" block { "Else If" expression "Then" block } [ "Else" block ] "End" ;
while_stmt     = "While" expression block "End" ;
for_stmt       = "For" IDENT "from" expression "to" expression [ "step" expression ] block "End" ;
for_each_stmt  = "For Each" IDENT "In" expression block "End" ;
repeat_stmt    = "Repeat" expression "Times" block "EndRepeat" ;
function_def   = "Define Function" IDENT [ "Takes" param_list ] block "EndFunction" ;
class_def      = "Class" IDENT [ "Inherits" IDENT ] class_body "EndClass" ;
module_def     = "Module" IDENT block "End" ;
import_stmt    = "Import" STRING [ "as" IDENT ] ;
use_stmt       = "Use python" STRING [ "as" IDENT ] ;
try_stmt       = "Try" block "Catch" IDENT block [ "Finally" block ] "EndTry" ;
match_stmt     = "Match" expression { "When" expr_list block } [ "Default" block ] "EndMatch" ;
return_stmt    = "Return" [ expression ] ;
throw_stmt     = "Throw" expression ;
assert_stmt    = "Assert" expression ;

expression     = or_expr ;
or_expr        = and_expr { ("Or" | "or") and_expr } ;
and_expr       = not_expr { ("And" | "and") not_expr } ;
not_expr       = [ "Not" | "not" ] comparison ;
comparison     = addition { comp_op addition } ;
addition       = multiplication { ("+" | "-") multiplication } ;
multiplication = unary { ("*" | "/" | "%") unary } ;
unary          = [ "-" | "Not" ] primary ;
primary        = NUMBER | STRING | "True" | "False" | "Nothing"
               | IDENT | list_literal | dict_literal
               | function_call | member_access | index_access
               | "(" expression ")" | lambda ;

param_list     = IDENT { "," IDENT } ;
block          = { statement } ;
```

---

## 19. Version History

| Version | Highlights |
|---------|-----------|
| 0.1 | Variables, Print, Input |
| 0.2 | If/Else, While, For |
| 0.3 | Functions, Import, Use |
| 0.4 | Classes, OOP, Inheritance |
| 0.5 | Try/Catch, Match/When |
| 0.6 | Built-in functions, Math |
| 0.7 | English aliases (Say, Ask, Remember) |
| 1.0 | String templates, list/dict comprehensions |
| 2.0 | LLVM compilation, JS transpilation |
| 3.0 | Web framework, GUI, Package manager |
| 4.0 | ORM, Debugger, LSP, Testing, AI, Bytecode VM |
| 4.1 | Advanced web: store backends, WebSocket, hot-reload |
| **4.2** | **Independent language: standalone CLI, native stdlib, binary packaging** |

---

*EPL v7.0.0 — Write code in plain English. Build anything.*
