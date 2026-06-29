"""Names the native backend treats specially — the single source of truth shared
by the compiler (which dispatches them) and the inference pass (which must refuse
to natively build a *user* function that collides with one).

Kept dependency-free (no llvmlite) so ``epl.native_infer`` can import it even in
environments without the LLVM toolchain installed.
"""

# Builtins the native compiler dispatches in ``_compile_function_call`` BEFORE
# user-defined functions. A user function with one of these names is therefore
# shadowed by the builtin natively, while the interpreter/VM let the user
# function win — so inference must not natively admit such a program (the outputs
# would diverge). Must stay in sync with the dispatch set in compiler.py.
NATIVE_BUILTIN_NAMES = frozenset(
    {
        'length',
        'type_of',
        'typeof',
        'to_integer',
        'to_text',
        'to_decimal',
        'to_boolean',
        'absolute',
        'round',
        'max',
        'min',
        'random',
        'uppercase',
        'lowercase',
        'sqrt',
        'power',
        'floor',
        'ceil',
        'log',
        'sin',
        'cos',
        'range',
        'sum',
        'sorted',
        'reversed',
        'is_integer',
        'is_decimal',
        'is_text',
        'is_boolean',
        'is_list',
        'is_nothing',
        'is_number',
        'char_code',
        'from_char_code',
    }
)

# Runtime intrinsics declared as ``epl_<name>`` in the module. A user function
# named ``<name>`` mangles to the same symbol and would build-fail on a duplicate
# definition, so inference declines it. Mirrors the plain-word ``epl_*`` math /
# system intrinsics in compiler.py.
RESERVED_RUNTIME_NAMES = frozenset(
    {
        'assert',
        'ceil',
        'clamp',
        'cos',
        'dlclose',
        'dlopen',
        'dlsym',
        'exit',
        'exp',
        'fabs',
        'floor',
        'input',
        'log',
        'log10',
        'power',
        'round',
        'sign',
        'sin',
        'sqrt',
        'system',
        'tan',
        'throw',
    }
)

# Any user function name the native backend cannot faithfully build a distinct,
# correctly-dispatched function for.
NATIVE_SHADOWED_NAMES = NATIVE_BUILTIN_NAMES | RESERVED_RUNTIME_NAMES
