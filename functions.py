#!/usr/bin/env python3
"""Auto-generated from EPL source."""


def sayHello():
    print('Hello from a function!')

sayHello()

def greet(name):
    print((('Hello, ' + name) + '! Welcome to EPL'))

greet('Abneesh')
greet('World')

def add(a, b):
    return (a + b)

result = add(5, 10)
print(('5 + 10 = ' + result))

def factorial(n):
    if (n <= 1):
        return 1
    return (n * factorial((n - 1)))

fact5 = factorial(5)
print(('Factorial of 5 = ' + fact5))

def countTo(limit):
    current = 1
    while (current <= limit):
        print(current)
        current = (current + 1)

print('Counting to 3:')
countTo(3)
