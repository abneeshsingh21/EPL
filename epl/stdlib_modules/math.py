"""
epl.stdlib_modules.math — Math domain public API.
"""

from __future__ import annotations

FUNCTIONS = frozenset(
    {
        'pi',
        'euler',
        'inf',
        'nan',
        'abs',
        'sin',
        'cos',
        'tan',
        'atan',
        'atan2',
        'asin',
        'acos',
        'sqrt',
        'log',
        'log2',
        'log10',
        'exp',
        'degrees',
        'radians',
        'gcd',
        'lcm',
        'factorial',
        'is_finite',
        'is_nan',
        'clamp',
        'lerp',
        'sign',
        'hypot',
        'sinh',
        'cosh',
        'tanh',
        'asinh',
        'acosh',
        'atanh',
        'ceil_div',
        'fmod',
        'copysign',
        'permutations',
        'combinations',
        'variance',
        'std_dev',
        'floor',
        'ceil',
        'round',
        'min',
        'max',
        'sum',
        'average',
        'power',
        'modulo',
    }
)

DOCS: dict[str, str] = {
    'pi': 'The mathematical constant π ≈ 3.14159.',
    'euler': "Euler's number e ≈ 2.71828.",
    'inf': 'Positive infinity.',
    'nan': 'Not-a-number sentinel.',
    'abs': 'Absolute value of a number.',
    'sin': 'Sine of an angle in radians.',
    'cos': 'Cosine of an angle in radians.',
    'tan': 'Tangent of an angle in radians.',
    'sqrt': 'Square root.',
    'log': 'Natural logarithm (base e).',
    'log2': 'Logarithm base 2.',
    'log10': 'Logarithm base 10.',
    'exp': 'e raised to the power x.',
    'degrees': 'Convert radians to degrees.',
    'radians': 'Convert degrees to radians.',
    'gcd': 'Greatest common divisor of two integers.',
    'lcm': 'Least common multiple of two integers.',
    'factorial': 'n! — factorial of n.',
    'clamp': 'Clamp a value between min and max.',
    'lerp': 'Linear interpolation between two values.',
    'sign': 'Sign of a number (-1, 0, or 1).',
    'hypot': 'Euclidean distance: sqrt(x² + y²).',
    'variance': 'Statistical variance of a list of numbers.',
    'std_dev': 'Standard deviation of a list of numbers.',
    'permutations': 'Number of ordered permutations P(n, r).',
    'combinations': 'Number of combinations C(n, r).',
    'floor': 'Round down to nearest integer.',
    'ceil': 'Round up to nearest integer.',
    'round': 'Round to nearest integer (or decimal places).',
    'min': 'Minimum value in a list.',
    'max': 'Maximum value in a list.',
    'sum': 'Sum of all values in a list.',
    'average': 'Average (mean) of a list.',
    'power': 'x raised to the power y.',
    'modulo': 'x modulo y (remainder).',
    'ceil_div': 'Ceiling division: ceil(a / b).',
}


def get_functions() -> frozenset[str]:
    return FUNCTIONS


def describe(fn_name: str) -> str:
    return DOCS.get(fn_name, f'{fn_name}: no documentation available.')
