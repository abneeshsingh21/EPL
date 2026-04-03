# EPL Tutorials

Step-by-step guides to learn EPL from beginner to advanced.

## Tutorial 1: Hello World

Create a file called `hello.epl`:

```epl
Say "Hello, World!"
```

Run it:

```bash
python main.py hello.epl
```

Output:
```
Hello, World!
```

---

## Tutorial 2: Variables and Math

```epl
Note: Creating variables
Create name equal to "Alice"
Create age equal to 25
Create height equal to 5.6

Note: Math operations
Create sum equal to age + 10
Create doubled equal to age * 2

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
Create temperature equal to 75

If temperature > 90 Then
    Say "It's hot outside!"
Otherwise If temperature > 70 Then
    Say "Nice weather!"
Otherwise If temperature > 50 Then
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
Create fruits equal to ["apple", "banana", "cherry"]
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

Create result equal to add(10, 20)
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
Create numbers equal to [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

Note: Filter even numbers
Create evens equal to numbers.filter(lambda x -> x % 2 == 0)
Say "Even numbers: " + evens

Note: Double each number
Create doubled equal to numbers.map(lambda x -> x * 2)
Say "Doubled: " + doubled

Note: Sum all numbers
Create total equal to numbers.reduce(lambda a, b -> a + b)
Say "Total: " + total

Note: Chain operations
Create result equal to numbers.filter(lambda x -> x > 5).map(lambda x -> x * x)
Say "Squares of numbers > 5: " + result
```

---

## Tutorial 7: Classes and Objects

```epl
Class BankAccount
    Set owner to ""
    Set balance to 0

    Method deposit takes amount
        Set balance to balance + amount
        Say owner + " deposited " + amount + ". Balance: " + balance
    End

    Method withdraw takes amount
        If amount > balance Then
            Say "Insufficient funds!"
        Otherwise
            Set balance to balance - amount
            Say owner + " withdrew " + amount + ". Balance: " + balance
        End
    End
End

Create account equal to new BankAccount
Set account.owner to "Alice"
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
    Create result equal to divide(10, 0)
    Say "Result: " + result
Catch error
    Say "Error caught: " + error
End

Note: Normal division
Try
    Create result2 equal to divide(10, 2)
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
Create content equal to read_file("data.txt")
Say "File says: " + content

Note: Write JSON
Create data equal to Map with name = "Alice" and scores = [95, 87, 92]
write_file("data.json", json_stringify(data))

Note: Read JSON
Create loaded equal to json_parse(read_file("data.json"))
Say "Name: " + loaded.name
```

---

## Tutorial 10: Building a Project

### Initialize a Project

```bash
python main.py init my-app
cd my-app
```

This creates:
- `epl.toml` — project manifest
- `main.epl` — entry point

### Install Packages

```bash
python main.py install epl-math
python main.py install epl-testing
```

### Run Your Project

```bash
python main.py main.epl
```

### Build Your Project

```bash
python main.py compile main.epl
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
python main.py validate .
python main.py pack .
python main.py publish .
```

### Use in another project

```bash
python main.py install my-utils
```

```epl
Import "my-utils"
Say double(21)     Note: 42
Say is_even(4)     Note: true
```
