# EPL Language Reference

Complete reference for the English Programming Language (EPL) v7.0.

## Table of Contents

1. [Variables](#variables)
2. [Data Types](#data-types)
3. [Operators](#operators)
4. [Control Flow](#control-flow)
5. [Functions](#functions)
6. [Classes & OOP](#classes--oop)
7. [Collections](#collections)
8. [Error Handling](#error-handling)
9. [Modules & Imports](#modules--imports)
10. [Built-in Functions](#built-in-functions)
11. [String Methods](#string-methods)
12. [List Methods](#list-methods)
13. [Map Methods](#map-methods)

---

## Variables

### Creating Variables

```epl
name = "Alice"
age = 25
pi = 3.14
active = true

Note: Type inference (type is optional)
score = 100
greeting = "Hello"
```

### Short Form

```epl
Remember name as "Alice"
Remember age as 25
```

### Setting Variables

```epl
name = "Bob"
age = 30
Increase age by 1
Decrease age by 1
```

### Constants

```epl
Constant PI = 3.14159
Note: Attempting to change PI will raise an error
```

### Augmented Assignment

```epl
x = 10
x = x + 5    Note: x is now 15
x = x * 2    Note: x is now 30
```

---

## Data Types

| Type | Example | EPL Name |
|------|---------|----------|
| Integer | `42`, `-5`, `0` | `integer` |
| Decimal | `3.14`, `-0.5` | `decimal` |
| Text | `"Hello"`, `'World'` | `text` |
| Boolean | `true`, `false`, `yes`, `no` | `boolean` |
| List | `[1, 2, 3]` | `list` |
| Map | `Map with name = "Alice"` | `map` |
| Nothing | `nothing` | `nothing` |

### Type Checking

```epl
Print type_of(42)          Note: "integer"
Print is_integer(42)
Note: true
Print is_text("hello")
Note: true
Print is_list([1, 2])      Note: true
Print is_number(3.14)      Note: true
Print is_nothing(nothing)  Note: true
```

---

## Operators

### Arithmetic

| Operator | Symbol | English Form |
|----------|--------|-------------|
| Addition | `+` | `add X to Y` |
| Subtraction | `-` | `subtract X from Y` |
| Multiplication | `*` | `multiply X by Y` |
| Division | `/` | `divide X by Y` |
| Modulo | `%` | `X modulo Y` |
| Power | `**` | `X raised to Y` |
| Floor Division | `//` | |
| Negation | `-X` | |

### Comparison

| Operator | Symbol | English Form |
|----------|--------|-------------|
| Equal | `==` | `equals`, `is equal to` |
| Not Equal | `!=` | `does not equal` |
| Greater Than | `>` | `is greater than` |
| Less Than | `<` | `is less than` |
| Greater or Equal | `>=` | `is at least` |
| Less or Equal | `<=` | `is at most` |
| Between | | `X is between A and B` |

### Logical

| Operator | Usage |
|----------|-------|
| `and` | `condition1 and condition2` (short-circuit) |
| `or` | `condition1 or condition2` (short-circuit) |
| `not` | `not condition` |

**Note:** `and`/`or` use short-circuit evaluation. The right side is only evaluated if needed.

```epl
items = []
If length(items) > 0 and items[0] == "hello" Then
    Note: items[0] is never accessed because length(items) > 0 is false
End
```

---

## Control Flow

### If/Otherwise

```epl
If age >= 18 Then
    Print "Adult"
Otherwise If age >= 13 Then
    Print "Teen"
Otherwise
    Print "Child"
End
```

### Match/When

```epl
Match day
    When "Monday" Print "Start of week"
    When "Friday" Print "Almost weekend"
    Default Print "Regular day"
End
```

### Ternary

```epl
result = "big" if x > 10 otherwise "small"
```

---

## Loops

### Repeat

```epl
Repeat 5 times
    Print "Hello"
End
```

### While

```epl
i = 0
While i < 10
    Print i
    Increase i by 1
End
```

### For Each

```epl
items = [1, 2, 3]
For Each item in items
    Print item
End
```

### For Range

```epl
For i from 1 to 10
    Print i
End

For i from 0 to 20 step 2
    Print i
End

For i from 10 to 1 step -1
    Print i
End
```

### Break & Continue

```epl
While true
    If condition Then
        Break
    End
    Continue
End
```

---

## Functions

### Defining Functions

```epl
Function greet
    Print "Hello!"
End

Function add takes a, b
    Return a + b
End

Note: With arrow syntax (lambdas only)
double = lambda x -> x * 2
```

### Calling Functions

```epl
greet()
result = add(3, 4)
Print double(5)
```

### Lambda Functions

```epl
square = lambda x -> x * x
Print square(5)    Note: 25

add = lambda a, b -> a + b
Print add(3, 4)    Note: 7
```

### Higher-Order Functions

```epl
Function apply takes fn, x
    Return fn(x)
End

result = apply(lambda x -> x * 2, 5)
Print result    Note: 10
```

---

## Classes & OOP

### Basic Class

```epl
Class Dog
    name = ""
    breed = ""

    Function speak
        Print name + " says Woof!"
    End
End

rex = new Dog
rex.name = "Rex"
rex.speak()
```

### Inheritance

```epl
Class Animal
    name = ""
    Function speak
        Print name + " makes a sound"
    End
End

Class Dog extends Animal
    Function speak
        Print name + " says Woof!"
    End
End
```

### Constructor Methods

```epl
Class Circle
    radius = 0
    Function area
        Return 3.14159 * radius * radius
    End
End
```

---

## Collections

### Lists

```epl
items = [1, 2, 3, 4, 5]
Print items[0]
Note: 1
Print length(items)     Note: 5

Note: Slicing
Print items[1:3]        Note: [2, 3]
Print items[0:2]        Note: [1, 3, 5]
```

### Maps (Dictionaries)

```epl
person = Map with name = "Alice" and age = 30
Print person.name       Note: Alice
person.age = 31
Print keys(person)      Note: [name, age]
```

### Enums

```epl
Enum Color Red, Green, Blue

Print Color.Red         Note: 0
```

---

## Error Handling

### Try/Catch

```epl
Try
    result = 10 / 0
Catch error
    Print "Error: " + error
End
```

### Throw

```epl
Function validate takes age
    If age < 0 Then
        Throw "Age cannot be negative"
    End
    Return age
End

Try
    validate(-1)
Catch err
    Print err
End
```

### Assert

```epl
Assert 2 + 2 == 4
Assert length("hello") == 5
```

---

## Modules & Imports

### Importing Files

```epl
Import "utils.epl"
Import "math_helpers.epl"
```

### Using Built-in Modules

```epl
Import "math" As Math
Print Math.PI
Print Math.sqrt(16)
```

---

## Built-in Functions

### Type Functions

| Function | Description | Example |
|----------|-------------|---------|
| `length(x)` | Length of string/list/map | `length("hello")` → `5` |
| `type_of(x)` | Type name as string | `type_of(42)` → `"integer"` |
| `to_integer(x)` | Convert to integer | `to_integer("42")` → `42` |
| `to_decimal(x)` | Convert to decimal | `to_decimal("3.14")` → `3.14` |
| `to_text(x)` | Convert to string | `to_text(42)` → `"42"` |
| `to_boolean(x)` | Convert to boolean | `to_boolean(1)` → `true` |

### Math Functions

| Function | Description | Example |
|----------|-------------|---------|
| `absolute(x)` | Absolute value | `absolute(-5)` → `5` |
| `round(x)` | Round to nearest int | `round(3.7)` → `4` |
| `floor(x)` | Round down | `floor(3.9)` → `3` |
| `ceil(x)` | Round up | `ceil(3.1)` → `4` |
| `sqrt(x)` | Square root | `sqrt(16)` → `4.0` |
| `power(x, y)` | x to the power of y | `power(2, 10)` → `1024` |
| `log(x)` | Natural logarithm | `log(2.718)` → `~1.0` |
| `sin(x)`, `cos(x)`, `tan(x)` | Trigonometric | `sin(0)` → `0.0` |
| `max(a, b, ...)` | Maximum value | `max(3, 7, 2)` → `7` |
| `min(a, b, ...)` | Minimum value | `min(3, 7, 2)` → `2` |
| `random(a, b)` | Random integer in range | `random(1, 10)` |

### Collection Functions

| Function | Description | Example |
|----------|-------------|---------|
| `range(n)` | List from 0 to n-1 | `range(5)` → `[0,1,2,3,4]` |
| `range(a, b)` | List from a to b-1 | `range(2, 5)` → `[2,3,4]` |
| `sum(list)` | Sum of numeric list | `sum([1,2,3])` → `6` |
| `sorted(list)` | Sorted copy | `sorted([3,1,2])` → `[1,2,3]` |
| `reversed(list)` | Reversed copy | `reversed([1,2,3])` → `[3,2,1]` |
| `keys(map)` | Map keys as list | `keys(person)` |
| `values(map)` | Map values as list | `values(person)` |

### String Functions

| Function | Description | Example |
|----------|-------------|---------|
| `upper(s)` | Uppercase | `upper("hi")` → `"HI"` |
| `lower(s)` | Lowercase | `lower("HI")` → `"hi"` |
| `trim(s)` | Remove whitespace | `trim("  hi  ")` → `"hi"` |
| `split(s, sep)` | Split into list | `split("a,b", ",")` → `["a","b"]` |
| `replace(s, old, new)` | Replace text | `replace("hi", "h", "H")` → `"Hi"` |

### I/O Functions

| Function | Description |
|----------|-------------|
| `Print x` / `Say x` / `Display x` | Output to console |
| `Ask "prompt"` | Read user input |
| `read_file(path)` | Read file contents |
| `write_file(path, content)` | Write to file |

### JSON Functions

| Function | Description |
|----------|-------------|
| `json_parse(str)` | Parse JSON string |
| `json_stringify(val)` | Convert to JSON |

---

## String Methods

```epl
s = "Hello World"
Print s.length()              Note: 11
Print s.upper()               Note: "HELLO WORLD"
Print s.lower()               Note: "hello world"
Print s.contains("World")     Note: true
Print s.starts_with("Hello")  Note: true
Print s.ends_with("World")    Note: true
Print s.replace("World", "EPL")  Note: "Hello EPL"
Print s.split(" ")            Note: ["Hello", "World"]
Print s.substring(0, 5)       Note: "Hello"
Print s.trim()                Note: "Hello World"
Print s.index_of("World")     Note: 6
Print s.count("l")            Note: 3
Print s.repeat(2)             Note: "Hello WorldHello World"
Print s.reverse()             Note: "dlroW olleH"
Print s.char_at(0)            Note: "H"
Print s.to_list()             Note: ["H","e","l","l","o"," ","W","o","r","l","d"]
```

---

## List Methods

```epl
items = [3, 1, 4, 1, 5]

Add 9 to items                Note: [3, 1, 4, 1, 5, 9]
items.remove(1)               Note: removes first 1
Print items.contains(4)       Note: true
Print items.index_of(4)       Note: 2
Print items.count(1)          Note: 1
items.sort()                  Note: sorts in-place
items.reverse()               Note: reverses in-place
Print items.join(", ")        Note: "9, 5, 4, 3, 1"
Print items.pop()             Note: removes & returns last
items.clear()                 Note: empties the list

Note: Functional methods
nums = [1, 2, 3, 4, 5]
Print nums.map(lambda x -> x * 2)       Note: [2, 4, 6, 8, 10]
Print nums.filter(lambda x -> x > 3)    Note: [4, 5]
Print nums.reduce(lambda a, b -> a + b) Note: 15
Print nums.find(lambda x -> x > 3)      Note: 4
Print nums.every(lambda x -> x > 0)     Note: true
Print nums.some(lambda x -> x > 4)      Note: true
```

---

## Map Methods

```epl
m = Map with x = 1 and y = 2
Print keys(m)          Note: [x, y]
Print values(m)        Note: [1, 2]
Print m.has("x")       Note: true
Print m.get("z", 0)    Note: 0 (default)
m.set("z", 3)
Print m.length()       Note: 3
m.clear()
```

---

## File I/O

```epl
Note: Writing
write_file("output.txt", "Hello, World!")

Note: Reading
content = read_file("output.txt")
Print content
```

---

## Templates

```epl
name = "World"
age = 25
Print "Hello, {name}! You are {age} years old."
```
