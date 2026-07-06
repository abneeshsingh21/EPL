# Your First Program in Plain English

New to coding? EPL is a programming language where every keyword is an ordinary
English word. This tutorial takes you from zero to writing real programs — loops,
conditions, functions — without learning a single cryptic symbol.

**No install needed to follow along:** open the
[EPL Playground](https://abneeshsingh21.github.io/EPL/playground) and type as you read.
To run it locally: `pip install eplang`.

---

## Hello, world

```epl
Say "Hello, world!"
```

`Say` prints text. Run it and you'll see:

```
Hello, world!
```

That's a complete program. Compare it to what most languages make you write for the
same thing — no `print()`, no `System.out.println`, no semicolons.

---

## Variables

A variable is a labelled box that holds a value:

```epl
name = "Ada"
age = 36

Say "Hello, " + name
```

```
Hello, Ada
```

The `+` joins pieces of text together. Numbers work as you'd expect:

```epl
price = 40
tax = 8
Say "Total: " + (price + tax)
```

```
Total: 48
```

---

## Making decisions

Programs choose what to do using `If`:

```epl
age = 20

If age is greater than 18 then
    Say "You can vote"
Otherwise
    Say "Too young to vote"
End
```

```
You can vote
```

Read it aloud — it's a sentence. `is greater than`, `is less than`, and
`is equal to` are the comparisons, spelled the way you'd say them.

---

## Repeating things

To do something several times, use a loop:

```epl
Repeat 3 times
    Say "Practice makes perfect"
End
```

To count through a range:

```epl
For i from 1 to 5
    Say "Step " + i
End
```

```
Step 1
Step 2
Step 3
Step 4
Step 5
```

---

## Working with lists

A list holds many values in order:

```epl
scores = [95, 87, 92]

total = 0
For Each s in scores
    total = total + s
End

Say "Total: " + total
Say "Average: " + (total / length(scores))
```

```
Total: 274
Average: 91.33333333333333
```

`For Each ... in` walks through every item. `length(...)` tells you how many there are.

---

## FizzBuzz — the classic first challenge

This is the program every new programmer writes: print numbers 1 to 15, but say
"Fizz" for multiples of 3, "Buzz" for multiples of 5, and "FizzBuzz" for both.
`%` gives the remainder after division, so a remainder of 0 means "divides evenly."

```epl
For i from 1 to 15
    If i % 15 is equal to 0 then
        Say "FizzBuzz"
    Otherwise if i % 3 is equal to 0 then
        Say "Fizz"
    Otherwise if i % 5 is equal to 0 then
        Say "Buzz"
    Otherwise
        Say i
    End
End
```

```
1
2
Fizz
4
Buzz
Fizz
7
8
Fizz
Buzz
11
Fizz
13
14
FizzBuzz
```

You just wrote a program that stumps a lot of interview candidates — and you can
read every line of it.

---

## Functions — naming a piece of work

A function bundles steps under a name so you can reuse them:

```epl
Function double takes n
    Return n * 2
End

Say double(21)
```

```
42
```

Functions can call themselves, which is how you express things like the Fibonacci
sequence:

```epl
Function fibonacci takes n
    If n is less than 2 then
        Return n
    End
    Return fibonacci(n - 1) + fibonacci(n - 2)
End

Say fibonacci(10)
```

```
55
```

---

## Where to go next

You now know variables, conditions, loops, lists, and functions — the core of every
programming language, in plain English.

- [Build a REST API in plain English](../guides/rest-api-in-plain-english.md)
- [Todo app with a real database](../guides/database.md)
- [Full tutorials index](../tutorials.md)
- [Keep experimenting in the Playground](https://abneeshsingh21.github.io/EPL/playground)

If EPL made programming click for you, [star it on GitHub](https://github.com/abneeshsingh21/EPL) —
it helps other beginners find it.
