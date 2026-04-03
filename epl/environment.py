"""
EPL Environment (Scope Manager) v4.1
Manages variable and function storage with nested scope support,
module namespacing, visibility modifiers, and scope depth limiting.
"""

import os
from epl.errors import NameError as EPLNameError

# Maximum scope chain depth — prevents stack overflow from unbounded recursion
_MAX_SCOPE_DEPTH = int(os.environ.get('EPL_MAX_SCOPE_DEPTH', '500'))


class Environment:
    """
    Represents a scope for variable/function storage.
    Supports nested scopes via parent chaining, modules, and visibility.
    Enforces a maximum scope depth to prevent memory exhaustion.
    """
    __slots__ = ('parent', 'name', 'variables', 'functions', 'modules', 'constants', '_depth')

    def __init__(self, parent=None, name: str = "global"):
        self.parent = parent
        self.name = name
        self.variables = {}
        self.functions = {}
        self.modules = {}       # v4.0: registered modules {name: Environment}
        self.constants = set()  # v4.0: names of read-only bindings
        self._depth = (parent._depth + 1) if parent else 0

    def define_variable(self, name: str, value, var_type: str = None):
        """Define a new variable in the current scope."""
        self.variables[name] = {
            "value": value,
            "type": var_type or self._infer_type(value),
        }

    def define_constant(self, name: str, value, var_type: str = None):
        """Define a constant (read-only) variable."""
        self.define_variable(name, value, var_type)
        self.constants.add(name)

    def set_variable(self, name: str, value):
        """Update an existing variable. Walks up scope chain."""
        if name in self.variables:
            if name in self.constants:
                from epl.errors import RuntimeError as EPLRuntimeError
                raise EPLRuntimeError(f'Cannot reassign constant "{name}".')
            expected_type = self.variables[name]["type"]
            actual_type = self._infer_type(value)
            if expected_type and actual_type != expected_type:
                # Allow integer to decimal promotion
                if expected_type == "decimal" and actual_type == "integer":
                    value = float(value)
                else:
                    from epl.errors import TypeError as EPLTypeError
                    raise EPLTypeError(
                        f'Cannot assign {actual_type} value to variable "{name}" of type {expected_type}.'
                    )
            self.variables[name]["value"] = value
            return
        if self.parent:
            self.parent.set_variable(name, value)
            return
        raise EPLNameError(f'Variable "{name}" has not been created yet. Use "Create" to define it first.')

    def get_variable(self, name: str):
        """Look up a variable. Walks up scope chain."""
        if name in self.variables:
            return self.variables[name]["value"]
        if self.parent:
            return self.parent.get_variable(name)
        raise EPLNameError(f'Variable "{name}" has not been created yet.')

    def has_variable(self, name: str) -> bool:
        """Check if a variable exists in any accessible scope."""
        if name in self.variables:
            return True
        if self.parent:
            return self.parent.has_variable(name)
        return False

    def define_function(self, name: str, func_def):
        """Register a function definition in the current scope."""
        self.functions[name] = func_def

    def get_function(self, name: str):
        """Look up a function. Walks up scope chain."""
        if name in self.functions:
            return self.functions[name]
        if self.parent:
            return self.parent.get_function(name)
        raise EPLNameError(f'Function "{name}" has not been defined yet.')

    def has_function(self, name: str) -> bool:
        """Check if a function exists in any accessible scope."""
        if name in self.functions:
            return True
        if self.parent:
            return self.parent.has_function(name)
        return False

    def register_module(self, name: str, mod_env):
        """Register a module namespace."""
        self.modules[name] = mod_env

    def get_module(self, name: str):
        """Look up a registered module."""
        if name in self.modules:
            return self.modules[name]
        if self.parent:
            return self.parent.get_module(name)
        raise EPLNameError(f'Module "{name}" has not been defined.')

    def create_child(self, name: str = "local") -> "Environment":
        """Create a new child scope. Enforces maximum depth."""
        if self._depth >= _MAX_SCOPE_DEPTH:
            from epl.errors import RuntimeError as EPLRuntimeError
            raise EPLRuntimeError(
                f"Maximum scope depth ({_MAX_SCOPE_DEPTH}) exceeded. "
                f"This usually means infinite recursion. Add a base case to stop recursion, "
                f"or set EPL_MAX_SCOPE_DEPTH env var to increase the limit."
            )
        return Environment(parent=self, name=name)

    def get_all_names(self) -> set:
        """Return all variable and function names accessible from this scope."""
        names = set(self.variables.keys()) | set(self.functions.keys())
        if self.parent:
            names |= self.parent.get_all_names()
        return names

    @staticmethod
    def _infer_type(value) -> str:
        """Infer EPL type from a Python value."""
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "decimal"
        if isinstance(value, str):
            return "text"
        if isinstance(value, list):
            return "list"
        if isinstance(value, dict):
            return "map"
        if value is None:
            return "nothing"
        return "unknown"
