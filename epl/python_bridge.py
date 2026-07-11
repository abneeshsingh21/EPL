"""Helpers for EPL's Python bridge.

This module isolates Python bridge wrapping, unwrapping, and call-dispatch
logic from the core interpreter so the bridge contract can evolve with a
smaller regression surface.
"""

from __future__ import annotations

import os as _os

from epl.errors import RuntimeError as EPLRuntimeError


class PythonModule:
    """Wrap a Python module/class/namespace for EPL attribute chaining."""

    def __init__(self, module, name):
        self.module = module
        self.name = name

    def get_attr(self, attr_name):
        """Get attribute, wrapping sub-modules and classes for chaining.
        Raises AttributeError for missing attributes instead of returning None."""
        if not hasattr(self.module, attr_name):
            raise AttributeError(f'{self.name} has no attribute "{attr_name}".')
        attr = getattr(self.module, attr_name)
        if isinstance(attr, type) or (
            hasattr(attr, '__module__') and hasattr(attr, '__dict__') and not callable(attr)
        ):
            return PythonModule(attr, f'{self.name}.{attr_name}')
        return attr

    def __call__(self, *args, **kwargs):
        """Instantiate/invoke the wrapped object.

        Classes are wrapped (not returned raw) so that chained access such as
        ``alias.datetime.now()`` works. A wrapped class must therefore still be
        callable so ``alias.Decimal("3.14")`` and storing-then-calling
        (``Set D to alias.Decimal`` … ``D("3.14")``) keep working. Args arrive
        already unwrapped by the interpreter's call path.
        """
        return self.module(*args, **kwargs)

    def __repr__(self):
        return f'<python module {self.name}>'


def _is_pure_iterable(value) -> bool:
    """True only for objects whose sole meaningful contract is being iterated.

    These are safe to eagerly materialise into an EPL list: exhausting them
    loses nothing because they carry no attribute payload a caller would want.
    A rich object (an HTTP response, a file handle, a model instance) is
    excluded even when it defines ``__iter__`` — collapsing it would strip its
    attributes and, for streams, consume data. The check is structural, so the
    bridge never hard-depends on ``requests``/``numpy``/etc.
    """
    import collections.abc as _abc
    import io as _io
    import types as _types

    # A file/stream object is iterable (line-by-line) yet rich and stateful:
    # materialising it would strip `.read`/`.name`/`.close` and leave it at EOF.
    # Exclude anything IO-like — by ABC or by advertising stream methods — so it
    # reaches the attribute-preserving PythonModule wrapper. Checked first, since
    # a file handle is also an Iterator.
    if isinstance(value, _io.IOBase):
        return False
    # Duck-typed stream check: `read`/`write`/`fileno` are file-specific. `close`
    # is deliberately NOT here — generators also expose `.close()` (with
    # `.send`/`.throw`), and those ARE pure iterables we want to materialise.
    if any(hasattr(value, attr) for attr in ('read', 'write', 'fileno')):
        return False

    # Generators and lazy iterators: iterating IS their whole purpose.
    if isinstance(value, (_types.GeneratorType, range, frozenset)):
        return True
    if isinstance(value, (_abc.KeysView, _abc.ValuesView, _abc.ItemsView)):
        return True
    # A bare iterator (defines __next__) with no rich attribute payload.
    if isinstance(value, _abc.Iterator):
        return True
    return False


def wrap_python_result(value, *, epl_dict_type, python_module_type=PythonModule, _seen=None):
    """Convert Python-native values to EPL-compatible values."""
    if value is None or isinstance(value, (int, float, bool, str)):
        return value

    if _seen is None:
        _seen = set()
    obj_id = id(value)
    if obj_id in _seen:
        return f'<circular ref {type(value).__name__}>'
    _seen.add(obj_id)

    try:
        if isinstance(value, dict):
            return epl_dict_type(
                {
                    k: wrap_python_result(
                        v,
                        epl_dict_type=epl_dict_type,
                        python_module_type=python_module_type,
                        _seen=_seen,
                    )
                    for k, v in value.items()
                }
            )
        if isinstance(value, (list, tuple)):
            return [
                wrap_python_result(
                    item,
                    epl_dict_type=epl_dict_type,
                    python_module_type=python_module_type,
                    _seen=_seen,
                )
                for item in value
            ]
        if isinstance(value, set):
            return [
                wrap_python_result(
                    item,
                    epl_dict_type=epl_dict_type,
                    python_module_type=python_module_type,
                    _seen=_seen,
                )
                for item in value
            ]
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')

        # NumPy (and other array-API) scalars/arrays, detected by duck-typing
        # so this module never hard-depends on numpy. A 0-d scalar exposes
        # ``.item()`` (-> native Python number); an N-d array exposes
        # ``.tolist()`` (-> nested Python list). Without this, numeric-package
        # results leak out as opaque ``<python module int64>`` wrappers — and a
        # numpy array iterated element-wise yields a list of those wrappers.
        if hasattr(value, 'dtype'):
            if getattr(value, 'ndim', None) == 0 and hasattr(value, 'item'):
                return wrap_python_result(
                    value.item(),
                    epl_dict_type=epl_dict_type,
                    python_module_type=python_module_type,
                    _seen=_seen,
                )
            if hasattr(value, 'tolist'):
                return wrap_python_result(
                    value.tolist(),
                    epl_dict_type=epl_dict_type,
                    python_module_type=python_module_type,
                    _seen=_seen,
                )

        type_name = type(value).__name__
        # Only collapse *pure* iterables into an EPL list: single-purpose
        # iterators/generators, ``range``, ``frozenset``, and dict views. A rich
        # object that merely happens to define ``__iter__`` (e.g. a
        # ``requests.Response``, which streams its body) must NOT be exhausted
        # into a list — that would strip its attributes (``.status_code``,
        # ``.headers``) and consume the stream. Such objects fall through to the
        # ``PythonModule`` wrapper below, preserving attribute access.
        if _is_pure_iterable(value):
            try:
                return [
                    wrap_python_result(
                        item,
                        epl_dict_type=epl_dict_type,
                        python_module_type=python_module_type,
                        _seen=_seen,
                    )
                    for item in value
                ]
            except (TypeError, StopIteration):
                pass

        if hasattr(value, '__dict__') or hasattr(value, '__class__'):
            return python_module_type(value, type_name)
        return value
    finally:
        _seen.discard(obj_id)


def unwrap_python_argument(value, *, epl_dict_type, python_module_type=PythonModule, _seen=None):
    """Convert EPL runtime values back into plain Python objects for Python calls."""
    if value is None or isinstance(value, (int, float, bool, str)):
        return value
    if isinstance(value, python_module_type):
        return value.module

    if _seen is None:
        _seen = set()
    obj_id = id(value)
    if obj_id in _seen:
        return None
    _seen.add(obj_id)

    try:
        if isinstance(value, epl_dict_type):
            return {
                key: unwrap_python_argument(
                    item,
                    epl_dict_type=epl_dict_type,
                    python_module_type=python_module_type,
                    _seen=_seen,
                )
                for key, item in value.data.items()
            }
        if isinstance(value, dict):
            if value.get('__is_module__'):
                return {
                    key: unwrap_python_argument(
                        item,
                        epl_dict_type=epl_dict_type,
                        python_module_type=python_module_type,
                        _seen=_seen,
                    )
                    for key, item in value.items()
                    if not key.startswith('__')
                }
            if 'value' in value and 'type' in value and len(value) == 2:
                return unwrap_python_argument(
                    value['value'],
                    epl_dict_type=epl_dict_type,
                    python_module_type=python_module_type,
                    _seen=_seen,
                )
            return {
                key: unwrap_python_argument(
                    item,
                    epl_dict_type=epl_dict_type,
                    python_module_type=python_module_type,
                    _seen=_seen,
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                unwrap_python_argument(
                    item,
                    epl_dict_type=epl_dict_type,
                    python_module_type=python_module_type,
                    _seen=_seen,
                )
                for item in value
            ]
        if isinstance(value, tuple):
            return tuple(
                unwrap_python_argument(
                    item,
                    epl_dict_type=epl_dict_type,
                    python_module_type=python_module_type,
                    _seen=_seen,
                )
                for item in value
            )
        if isinstance(value, set):
            return {
                unwrap_python_argument(
                    item,
                    epl_dict_type=epl_dict_type,
                    python_module_type=python_module_type,
                    _seen=_seen,
                )
                for item in value
            }
        return value
    finally:
        _seen.discard(obj_id)


def resolve_python_module(module_name, line):
    """Resolve a Python module name, checking official packages first."""
    import importlib as _importlib
    import importlib.util as _importlib_util

    from epl.package_manager import OFFICIAL_PACKAGES_DIR

    pkg_dir_name = module_name.replace('_', '-')
    pkg_python_dir = _os.path.join(OFFICIAL_PACKAGES_DIR, pkg_dir_name, 'python')
    if _os.path.isdir(pkg_python_dir):
        init_file = _os.path.join(pkg_python_dir, '__init__.py')
        if _os.path.isfile(init_file):
            spec = _importlib_util.spec_from_file_location(module_name, init_file)
            mod = _importlib_util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    try:
        return _importlib.import_module(module_name)
    except ImportError:
        raise EPLRuntimeError(
            f'Cannot find Python module "{module_name}". Looked in: {pkg_python_dir} and sys.path.',
            line,
        ) from None


def call_python_function(
    module_name,
    module,
    func_name,
    func_args,
    line,
    *,
    epl_dict_type,
    python_module_type=PythonModule,
):
    """Call a Python function and convert arguments/results across the EPL boundary."""
    if not hasattr(module, func_name):
        raise EPLRuntimeError(f'Python module "{module_name}" has no function "{func_name}".', line)

    func = getattr(module, func_name)
    if not callable(func):
        return wrap_python_result(
            func,
            epl_dict_type=epl_dict_type,
            python_module_type=python_module_type,
        )

    try:
        result = func(
            *[
                unwrap_python_argument(
                    arg,
                    epl_dict_type=epl_dict_type,
                    python_module_type=python_module_type,
                )
                for arg in func_args
            ]
        )
        return wrap_python_result(
            result,
            epl_dict_type=epl_dict_type,
            python_module_type=python_module_type,
        )
    except TypeError as e:
        raise EPLRuntimeError(f'{module_name}.{func_name}() argument error: {e}', line) from e
    except Exception as e:
        raise EPLRuntimeError(f'Python error in {module_name}.{func_name}(): {e}', line) from e


def call_python_method(
    py_mod,
    method,
    args,
    line,
    *,
    epl_dict_type,
    python_module_type=PythonModule,
):
    """Call a function or access an attribute on a wrapped Python module."""
    if not hasattr(py_mod.module, method):
        raise EPLRuntimeError(f'Python module "{py_mod.name}" has no function "{method}".', line)

    attr = getattr(py_mod.module, method)
    if not callable(attr):
        return wrap_python_result(
            attr,
            epl_dict_type=epl_dict_type,
            python_module_type=python_module_type,
        )

    try:
        result = attr(
            *[
                unwrap_python_argument(
                    arg,
                    epl_dict_type=epl_dict_type,
                    python_module_type=python_module_type,
                )
                for arg in args
            ]
        )
        return wrap_python_result(
            result,
            epl_dict_type=epl_dict_type,
            python_module_type=python_module_type,
        )
    except TypeError as e:
        raise EPLRuntimeError(f'{py_mod.name}.{method}() argument error: {e}', line) from e
    except Exception as e:
        raise EPLRuntimeError(f'Python error in {py_mod.name}.{method}(): {e}', line) from e
