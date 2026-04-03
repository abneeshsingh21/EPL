#!/usr/bin/env python3
"""Auto-generated from EPL source."""

import sys

scores = [95, 87, 72, 91, 68]
print(('First score: ' + scores[0]))
print(('Last score: ' + scores[4]))
scores[2] = 100
print(f'Updated scores: {scores}')
total = 0
for i in range(1, 10 + 1):
    total = (total + i)
print(f'Sum of 1 to 10: {total}')
score = 85
if (score > 90):
    print('Grade: A')
elif (score > 80):
    print('Grade: B')
elif (score > 70):
    print('Grade: C')
else:
    print('Grade: F')
PI = 3.14159  # constant
APP_NAME = 'EPL Calculator'  # constant
print(f'{APP_NAME} uses PI = {PI}')
import math as math
print(('Square root of 144: ' + math.sqrt(144)))
print(('PI from Python: ' + math.pi))
assert ((1 + 1) == 2)
assert (len('hello') == 5)
assert (PI > 3)
print('All assertions passed')
try:
    result = (10 / 0)
except Exception as error:
    print(f'Caught: {error}')
day = 'Saturday'
match day:
    case 'Monday':
        print('Work day')
    case 'Saturday':
        print('Weekend!')
    case _:
        print('Regular day')
student = {'name': 'Abneesh', 'grade': 'A', 'score': 95}
for key in student:
    print(key)
print(((('Student: ' + student.name) + ' got ') + student.grade))
print('Done! EPL v0.3 is complete')
sys.exit(0)
print('This line will never run')
