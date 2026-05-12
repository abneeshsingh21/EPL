"""
EPL Array Package - Python Backend
NumPy-powered array operations for EPL.
"""

import numpy as np
from numpy import linalg

# ═══════════════════════════════════════════════════════════
#  Array Creation
# ═══════════════════════════════════════════════════════════


def create_array(data):
    """Create a NumPy array from a list."""
    return np.array(data)


def zeros(shape):
    """Create an array filled with zeros."""
    return np.zeros(shape)


def ones(shape):
    """Create an array filled with ones."""
    return np.ones(shape)


def arange(start, stop, step=1):
    """Create array with evenly spaced values."""
    return np.arange(start, stop, step)


def linspace(start, stop, num=50):
    """Create array with num evenly spaced values."""
    return np.linspace(start, stop, num)


def random(shape):
    """Create array with random values in [0, 1)."""
    return np.random.random(shape)


def randint(low, high, shape):
    """Create array with random integers."""
    return np.random.randint(low, high, shape)


def eye(n):
    """Create identity matrix."""
    return np.eye(n)


# ═══════════════════════════════════════════════════════════
#  Array Properties
# ═══════════════════════════════════════════════════════════


def shape(array):
    """Get array shape."""
    return np.asarray(array).shape


def size(array):
    """Get total number of elements."""
    return np.asarray(array).size


def ndim(array):
    """Get number of dimensions."""
    return np.asarray(array).ndim


def dtype(array):
    """Get data type of elements."""
    return str(np.asarray(array).dtype)


# ═══════════════════════════════════════════════════════════
#  Array Manipulation
# ═══════════════════════════════════════════════════════════


def reshape(array, new_shape):
    """Reshape an array."""
    return np.asarray(array).reshape(new_shape)


def flatten(array):
    """Flatten array to 1D."""
    return np.asarray(array).flatten()


def transpose(array):
    """Transpose array."""
    return np.asarray(array).T


def concatenate(arrays, axis=0):
    """Concatenate arrays along axis."""
    return np.concatenate([np.asarray(a) for a in arrays], axis=axis)


def stack(arrays, axis=0):
    """Stack arrays along new axis."""
    return np.stack([np.asarray(a) for a in arrays], axis=axis)


def split(array, sections, axis=0):
    """Split array into sections."""
    return np.split(np.asarray(array), sections, axis=axis)


def slice(array, start, end):
    """Slice array from start to end."""
    return np.asarray(array)[start:end]


# ═══════════════════════════════════════════════════════════
#  Element-wise Math
# ═══════════════════════════════════════════════════════════


def add(a, b):
    """Add two arrays element-wise."""
    return np.add(np.asarray(a), np.asarray(b))


def subtract(a, b):
    """Subtract two arrays element-wise."""
    return np.subtract(np.asarray(a), np.asarray(b))


def multiply(a, b):
    """Multiply two arrays element-wise."""
    return np.multiply(np.asarray(a), np.asarray(b))


def divide(a, b):
    """Divide two arrays element-wise."""
    return np.divide(np.asarray(a), np.asarray(b))


def power(array, exponent):
    """Raise array to power."""
    return np.power(np.asarray(array), exponent)


def sqrt(array):
    """Square root."""
    return np.sqrt(np.asarray(array))


def exp(array):
    """Exponential (e^x)."""
    return np.exp(np.asarray(array))


def log(array):
    """Natural logarithm."""
    return np.log(np.asarray(array))


def abs(array):
    """Absolute value."""
    return np.abs(np.asarray(array))


def sin(array):
    """Sine."""
    return np.sin(np.asarray(array))


def cos(array):
    """Cosine."""
    return np.cos(np.asarray(array))


def tan(array):
    """Tangent."""
    return np.tan(np.asarray(array))


# ═══════════════════════════════════════════════════════════
#  Statistics
# ═══════════════════════════════════════════════════════════


def sum(array):
    """Sum of elements."""
    return np.sum(np.asarray(array))


def mean(array):
    """Mean of elements."""
    return np.mean(np.asarray(array))


def median(array):
    """Median of elements."""
    return np.median(np.asarray(array))


def std(array):
    """Standard deviation."""
    return np.std(np.asarray(array))


def var(array):
    """Variance."""
    return np.var(np.asarray(array))


def min(array):
    """Minimum value."""
    return np.min(np.asarray(array))


def max(array):
    """Maximum value."""
    return np.max(np.asarray(array))


def argmin(array):
    """Index of minimum."""
    return np.argmin(np.asarray(array))


def argmax(array):
    """Index of maximum."""
    return np.argmax(np.asarray(array))


def percentile(array, q):
    """Percentile."""
    return np.percentile(np.asarray(array), q)


# ═══════════════════════════════════════════════════════════
#  Linear Algebra
# ═══════════════════════════════════════════════════════════


def dot(a, b):
    """Dot product."""
    return np.dot(np.asarray(a), np.asarray(b))


def matmul(a, b):
    """Matrix multiplication."""
    return np.matmul(np.asarray(a), np.asarray(b))


def inv(matrix):
    """Matrix inverse."""
    return linalg.inv(np.asarray(matrix))


def det(matrix):
    """Matrix determinant."""
    return linalg.det(np.asarray(matrix))


def eigvals(matrix):
    """Eigenvalues."""
    return linalg.eigvals(np.asarray(matrix))


def eig(matrix):
    """Eigenvalues and eigenvectors."""
    vals, vecs = linalg.eig(np.asarray(matrix))
    return {'values': vals, 'vectors': vecs}


def solve(a, b):
    """Solve linear system Ax = b."""
    return linalg.solve(np.asarray(a), np.asarray(b))


def norm(array, ord=None):
    """Vector/matrix norm."""
    return linalg.norm(np.asarray(array), ord=ord)


def trace(matrix):
    """Matrix trace."""
    return np.trace(np.asarray(matrix))


def rank(matrix):
    """Matrix rank."""
    return linalg.matrix_rank(np.asarray(matrix))


# ═══════════════════════════════════════════════════════════
#  Comparison & Logic
# ═══════════════════════════════════════════════════════════


def array_equal(a, b):
    """Check if arrays are equal."""
    return np.array_equal(np.asarray(a), np.asarray(b))


def where(condition, x, y):
    """Conditional selection."""
    return np.where(np.asarray(condition), np.asarray(x), np.asarray(y))


def all(array):
    """Check if all True."""
    return np.all(np.asarray(array))


def any(array):
    """Check if any True."""
    return np.any(np.asarray(array))


# ═══════════════════════════════════════════════════════════
#  Sorting & Searching
# ═══════════════════════════════════════════════════════════


def sort(array):
    """Sort array."""
    return np.sort(np.asarray(array))


def argsort(array):
    """Indices that would sort array."""
    return np.argsort(np.asarray(array))


def unique(array):
    """Unique elements."""
    return np.unique(np.asarray(array))


def searchsorted(array, value):
    """Find insertion index."""
    return np.searchsorted(np.asarray(array), value)
