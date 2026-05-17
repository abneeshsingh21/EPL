# EPL Tutorials

Step-by-step guides to learn EPL from beginner to advanced.

## Tutorial 1: Hello World

Create a file called `hello.epl`:

```epl
Say "Hello, World!"
```

Run it:

```bash
epl hello.epl
```

Output:
```
Hello, World!
```

---

## Tutorial 2: Variables and Math

```epl
Note: Creating variables
name = "Alice"
age = 25
height = 5.6

Note: Math operations
sum = age + 10
doubled = age * 2

Say "Name: " + name
Say "Age in 10 years: " + sum
Say "Is adult: " + (age >= 18)
```

Output:
```
Name: Alice
Age in 10 years: 35
Is adult: true
```

---

## Tutorial 3: Making Decisions

```epl
temperature = 75

If temperature > 90 then
    Say "It's hot outside!"
Otherwise If temperature > 70 then
    Say "Nice weather!"
Otherwise If temperature > 50 then
    Say "A bit chilly."
Otherwise
    Say "Bundle up!"
End
```

Output:
```
Nice weather!
```

---

## Tutorial 4: Loops

```epl
Note: Count from 1 to 5
For i from 1 to 5
    Say "Count: " + i
End

Note: Loop through a list
fruits = ["apple", "banana", "cherry"]
For each fruit in fruits
    Say "I like " + fruit
End

Note: Repeat something
Repeat 3 times
    Say "EPL is fun!"
End
```

---

## Tutorial 5: Functions

```epl
Note: Simple function
Function greet takes name
    Say "Hello, " + name + "!"
End

greet("Alice")
greet("Bob")

Note: Function with return value
Function add takes a, b
    Return a + b
End

result = add(10, 20)
Say "10 + 20 = " + result

Note: Recursive function
Function factorial takes n
    If n <= 1 Then
        Return 1
    End
    Return n * factorial(n - 1)
End

Say "5! = " + factorial(5)
```

Output:
```
Hello, Alice!
Hello, Bob!
10 + 20 = 30
5! = 120
```

---

## Tutorial 6: Lists and Functional Programming

```epl
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

Note: Filter even numbers
evens = numbers.filter(lambda x -> x % 2 == 0)
Say "Even numbers: " + evens

Note: Double each number
doubled = numbers.map(lambda x -> x * 2)
Say "Doubled: " + doubled

Note: Sum all numbers
total = numbers.reduce(lambda a, b -> a + b)
Say "Total: " + total

Note: Chain operations
result = numbers.filter(lambda x -> x > 5).map(lambda x -> x * x)
Say "Squares of numbers > 5: " + result
```

---

## Tutorial 7: Classes and Objects

```epl
Class BankAccount
    owner = ""
    balance = 0

    Function deposit takes amount
        balance = balance + amount
        Say owner + " deposited " + amount + ". Balance: " + balance
    End

    Function withdraw takes amount
        If amount > balance then
            Say "Insufficient funds!"
        Otherwise
            balance = balance - amount
            Say owner + " withdrew " + amount + ". Balance: " + balance
        End
    End
End

account = new BankAccount
account.owner = "Alice"
account.deposit(100)
account.deposit(50)
account.withdraw(30)
account.withdraw(200)
```

Output:
```
Alice deposited 100. Balance: 100
Alice deposited 50. Balance: 150
Alice withdrew 30. Balance: 120
Insufficient funds!
```

---

## Tutorial 8: Error Handling

```epl
Function divide takes a, b
    If b == 0 Then
        Throw "Cannot divide by zero!"
    End
    Return a / b
End

Note: Safe division
Try
    result = divide(10, 0)
    Say "Result: " + result
Catch error
    Say "Error caught: " + error
End

Note: Normal division
Try
    result2 = divide(10, 2)
    Say "Result: " + result2
Catch error
    Say "Error: " + error
End
```

Output:
```
Error caught: Cannot divide by zero!
Result: 5
```

---

## Tutorial 9: Working with Files

```epl
Note: Write a file
write_file("data.txt", "Hello from EPL!")

Note: Read it back
content = read_file("data.txt")
Say "File says: " + content

Note: Write JSON
data = Map with name = "Alice" and scores = [95, 87, 92]
write_file("data.json", json_stringify(data))

Note: Read JSON
loaded = json_parse(read_file("data.json"))
Say "Name: " + loaded.name
```

---

## Tutorial 10: Building a Project

### Initialize a Project

```bash
epl init my-app
cd my-app
```

This creates:
- `epl.toml` — project manifest
- `main.epl` — entry point

### Install Packages

```bash
epl install epl-math
epl install epl-test
```

### Run Your Project

```bash
epl main.epl
```

### Build Your Project

```bash
epl build main.epl
```

---

## Tutorial 11: Package Management

### Create a reusable package

Create `epl.toml`:
```toml
[project]
name = "my-utils"
version = "1.0.0"
description = "My utility functions"
entry = "main.epl"

[dependencies]
```

Create `main.epl`:
```epl
Function double takes x
    Return x * 2
End

Function is_even takes n
    Return n % 2 == 0
End
```

### Validate and publish

```bash
epl check main.epl
epl pack .
epl publish .
```

### Use in another project

```bash
epl install my-utils
```

```epl
Import "my-utils"
Say double(21)     Note: 42
Say is_even(4)     Note: true
```
