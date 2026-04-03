#!/usr/bin/env python3
"""Auto-generated from EPL source."""


class Animal:
    def __init__(self):
        self.name = 'Unknown'
        self.sound = '...'


    def speak():
        print(((self.name + ' says ') + self.sound))


dog = Animal()
dog.name = 'Rex'
dog.sound = 'Woof!'
cat = Animal()
cat.name = 'Whiskers'
cat.sound = 'Meow!'
dog.speak()
cat.speak()
print(('Dog\'s name: ' + dog.name))
print(('Cat\'s sound: ' + cat.sound))

class Calculator:
    def __init__(self):
        self.result = 0


    def add(a, b):
        return (a + b)


    def multiply(a, b):
        return (a * b)


calc = Calculator()
sum = calc.append(10, 20)
print(('10 + 20 = ' + sum))
product = calc.multiply(6, 7)
print(('6 * 7 = ' + product))
