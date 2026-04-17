"""
EPL Compiler (v1.0)
Compiles EPL AST -> LLVM IR -> native executable.
Full feature support: variables, math, strings, lists, maps,
if/while/for/repeat/for-each, functions, classes, imports, print, input,
file I/O, try/catch, break/continue, match/when, constants, assert, wait,
exit, augmented assignment, lambda, ternary, power, floor div, slicing,
enums, throw, string/list/map methods.
"""

import re as _re
import warnings as _warnings

try:
    import llvmlite.ir as ir  # type: ignore[reportMissingImports]
    import llvmlite.binding as llvm  # type: ignore[reportMissingImports]
    # Initialize LLVM - handle both old and new llvmlite versions
    _llvm_initialized = False
    for _init_fn in [llvm.initialize, llvm.initialize_native_target, llvm.initialize_native_asmprinter]:
        try:
            _init_fn()
            _llvm_initialized = True
        except RuntimeError:
            pass  # newer llvmlite auto-initializes
    # If auto-init didn't register targets, force it via all-targets
    if not _llvm_initialized:
        try:
            llvm.initialize_all_targets()
            llvm.initialize_all_asmprinters()
        except (RuntimeError, AttributeError):
            pass
    HAS_LLVM = True
except Exception:
    ir = None  # type: ignore
    llvm = None  # type: ignore
    HAS_LLVM = False

from epl import ast_nodes as ast
from epl.errors import RuntimeError as EPLRuntimeError

TAG_INT = 0
TAG_FLOAT = 1
TAG_BOOL = 2
TAG_STRING = 3
TAG_NONE = 4
TAG_LIST = 5
TAG_MAP = 6
TAG_OBJECT = 7


def _mangle_name(name: str) -> str:
    """Mangle non-ASCII identifier names to be LLVM IR safe."""
    if name.isascii():
        return name
    parts = []
    for ch in name:
        if ch.isascii() and (ch.isalnum() or ch == '_'):
            parts.append(ch)
        else:
            parts.append(f'_U{ord(ch):04X}_')
    return ''.join(parts)


class Compiler:
    """Compiles an EPL AST to LLVM IR and optionally to a native executable."""

    # Supported optimization levels:
    #   0 = no optimization (fastest compile, best debug)
    #   1 = basic optimizations (constant folding, dead code elimination)
    #   2 = standard optimizations (default — inlining, loop opts, vectorization)
    #   3 = aggressive (all of O2 + loop unrolling, auto-vectorization)
    VALID_OPT_LEVELS = (0, 1, 2, 3)

    def __init__(self, opt_level=2, debug=False, source_filename="<input>"):
        if not HAS_LLVM:
            raise ImportError("llvmlite is required for compilation. Install with: pip install llvmlite")
        if opt_level not in self.VALID_OPT_LEVELS:
            raise ValueError(f"opt_level must be one of {self.VALID_OPT_LEVELS}, got {opt_level}")
        self.opt_level = opt_level
        self.debug = debug
        self.source_filename = source_filename
        self.module = ir.Module(name="epl_program")
        self.module.triple = llvm.get_default_triple()
        # Set data layout from default target machine for correct optimization
        _target = llvm.Target.from_default_triple()
        _tm = _target.create_target_machine()
        self.module.data_layout = str(_tm.target_data)
        self.i8 = ir.IntType(8)
        self.i32 = ir.IntType(32)
        self.i64 = ir.IntType(64)
        self.f64 = ir.DoubleType()
        self.void = ir.VoidType()
        self.i8_ptr = self.i8.as_pointer()
        self.i1 = ir.IntType(1)
        self.epl_value_type = ir.LiteralStructType([self.i8, self.i64])
        self.builder = None
        self.func = None
        self.variables = {}
        self.functions = {}
        self.string_constants = {}
        self.break_block = None
        self.continue_block = None
        self.var_types = {}
        self.lambda_counter = 0
        # Debug info state
        self._di_file = None
        self._di_cu = None
        self._di_subprogram = None
        self._declare_runtime()

    def _init_debug_info(self):
        """Initialize DWARF debug metadata (DICompileUnit, DIFile)."""
        import os
        fname = os.path.basename(self.source_filename)
        dname = os.path.dirname(os.path.abspath(self.source_filename))
        self._di_file = self.module.add_debug_info('DIFile', {
            'filename': fname,
            'directory': dname,
        })
        self._di_cu = self.module.add_debug_info('DICompileUnit', {
            'language': ir.DIToken('DW_LANG_C'),
            'file': self._di_file,
            'producer': 'EPL Compiler v5.0',
            'runtimeVersion': 0,
            'isOptimized': self.opt_level > 0,
        })

    def _attach_debug_to_function(self, func, name, line):
        """Attach a DISubprogram to an IR function."""
        if not self.debug:
            return
        di_sub_type = self.module.add_debug_info('DISubroutineType', {
            'types': self.module.add_metadata([]),
        })
        di_sub = self.module.add_debug_info('DISubprogram', {
            'name': name,
            'file': self._di_file,
            'line': line,
            'type': di_sub_type,
            'isLocal': name != 'main',
            'unit': self._di_cu,
        })
        func.set_metadata('dbg', di_sub)
        self._di_subprogram = di_sub

    def _set_debug_loc(self, line):
        """Set the debug location on the current builder for the given source line."""
        if not self.debug or self._di_subprogram is None or self.builder is None:
            return
        di_loc = self.module.add_debug_info('DILocation', {
            'line': max(line, 1),
            'column': 0,
            'scope': self._di_subprogram,
        })
        self.builder.debug_metadata = di_loc

    def _declare_runtime(self):
        printf_ty = ir.FunctionType(self.i32, [self.i8_ptr], var_arg=True)
        self.printf = ir.Function(self.module, printf_ty, name="printf")

        puts_ty = ir.FunctionType(self.i32, [self.i8_ptr])
        self.puts = ir.Function(self.module, puts_ty, name="puts")

        sprintf_ty = ir.FunctionType(self.i32, [self.i8_ptr, self.i8_ptr], var_arg=True)
        self.sprintf = ir.Function(self.module, sprintf_ty, name="sprintf")

        malloc_ty = ir.FunctionType(self.i8_ptr, [self.i64])
        self.malloc = ir.Function(self.module, malloc_ty, name="malloc")

        free_ty = ir.FunctionType(self.void, [self.i8_ptr])
        self.free = ir.Function(self.module, free_ty, name="free")

        strlen_ty = ir.FunctionType(self.i64, [self.i8_ptr])
        self.strlen = ir.Function(self.module, strlen_ty, name="strlen")

        strcpy_ty = ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr])
        self.strcpy = ir.Function(self.module, strcpy_ty, name="strcpy")

        strcat_ty = ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr])
        self.strcat = ir.Function(self.module, strcat_ty, name="strcat")

        strcmp_ty = ir.FunctionType(self.i32, [self.i8_ptr, self.i8_ptr])
        self.strcmp = ir.Function(self.module, strcmp_ty, name="strcmp")

        exit_ty = ir.FunctionType(self.void, [self.i32])
        self.exit_fn = ir.Function(self.module, exit_ty, name="exit")

        sleep_ty = ir.FunctionType(self.void, [self.i32])
        self.sleep_fn = ir.Function(self.module, sleep_ty, name="_sleep")

        file_ptr = self.i8_ptr
        fopen_ty = ir.FunctionType(file_ptr, [self.i8_ptr, self.i8_ptr])
        self.fopen = ir.Function(self.module, fopen_ty, name="fopen")
        fclose_ty = ir.FunctionType(self.i32, [file_ptr])
        self.fclose = ir.Function(self.module, fclose_ty, name="fclose")
        fprintf_ty = ir.FunctionType(self.i32, [file_ptr, self.i8_ptr], var_arg=True)
        self.fprintf = ir.Function(self.module, fprintf_ty, name="fprintf")

        # EPL Runtime Library
        self.rt_list_new = ir.Function(self.module, ir.FunctionType(self.i8_ptr, []), name="epl_list_new")
        self.rt_list_push = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr, self.i32, self.i64]), name="epl_list_push_raw")
        self.rt_list_get_int = ir.Function(self.module, ir.FunctionType(self.i64, [self.i8_ptr, self.i64]), name="epl_list_get_int")
        self.rt_list_get_tag = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr, self.i64]), name="epl_list_get_tag")
        self.rt_list_set_int = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr, self.i64, self.i64]), name="epl_list_set_int")
        self.rt_list_length = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr]), name="epl_list_length")
        self.rt_list_remove = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr, self.i64]), name="epl_list_remove_raw")
        self.rt_list_contains_int = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr, self.i64]), name="epl_list_contains_int")
        self.rt_list_slice = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i64, self.i64, self.i64]), name="epl_list_slice")
        self.rt_list_print = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr]), name="epl_list_print")

        self.rt_map_new = ir.Function(self.module, ir.FunctionType(self.i8_ptr, []), name="epl_map_new")
        self.rt_map_set_int = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr, self.i8_ptr, self.i64]), name="epl_map_set_int")
        self.rt_map_set_str = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr, self.i8_ptr, self.i8_ptr]), name="epl_map_set_str")
        self.rt_map_get_int = ir.Function(self.module, ir.FunctionType(self.i64, [self.i8_ptr, self.i8_ptr]), name="epl_map_get_int")
        self.rt_map_get_str = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr]), name="epl_map_get_str")

        self.rt_obj_new = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_object_new")
        self.rt_obj_set_int = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr, self.i8_ptr, self.i64]), name="epl_object_set_int")
        self.rt_obj_set_str = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr, self.i8_ptr, self.i8_ptr]), name="epl_object_set_str")
        self.rt_obj_get_int = ir.Function(self.module, ir.FunctionType(self.i64, [self.i8_ptr, self.i8_ptr]), name="epl_object_get_int")
        self.rt_obj_get_str = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr]), name="epl_object_get_str")

        self.rt_str_index = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i64]), name="epl_string_index")
        self.rt_str_length = ir.Function(self.module, ir.FunctionType(self.i64, [self.i8_ptr]), name="epl_string_length")
        self.rt_str_upper = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_string_upper")
        self.rt_str_lower = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_string_lower")
        self.rt_str_contains = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr, self.i8_ptr]), name="epl_string_contains")
        self.rt_str_substring = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i64, self.i64]), name="epl_string_substring")
        self.rt_str_replace = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr, self.i8_ptr]), name="epl_string_replace")
        self.rt_str_trim = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_string_trim")
        self.rt_str_starts_with = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr, self.i8_ptr]), name="epl_string_starts_with")
        self.rt_str_ends_with = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr, self.i8_ptr]), name="epl_string_ends_with")
        self.rt_str_split = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr]), name="epl_string_split")
        self.rt_str_reverse = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_string_reverse")

        self.rt_input = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_input")
        self.rt_input_no = ir.Function(self.module, ir.FunctionType(self.i8_ptr, []), name="epl_input_no_prompt")

        self.rt_int_to_str = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i64]), name="epl_int_to_string")
        self.rt_float_to_str = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.f64]), name="epl_float_to_string")
        self.rt_str_to_int = ir.Function(self.module, ir.FunctionType(self.i64, [self.i8_ptr]), name="epl_string_to_int")
        self.rt_str_to_float = ir.Function(self.module, ir.FunctionType(self.f64, [self.i8_ptr]), name="epl_string_to_float")

        self.rt_power = ir.Function(self.module, ir.FunctionType(self.f64, [self.f64, self.f64]), name="epl_power")
        self.rt_floor = ir.Function(self.module, ir.FunctionType(self.f64, [self.f64]), name="epl_floor")
        self.rt_sqrt = ir.Function(self.module, ir.FunctionType(self.f64, [self.f64]), name="epl_sqrt")
        self.rt_ceil = ir.Function(self.module, ir.FunctionType(self.f64, [self.f64]), name="epl_ceil")
        self.rt_log = ir.Function(self.module, ir.FunctionType(self.f64, [self.f64]), name="epl_log")
        self.rt_sin = ir.Function(self.module, ir.FunctionType(self.f64, [self.f64]), name="epl_sin")
        self.rt_cos = ir.Function(self.module, ir.FunctionType(self.f64, [self.f64]), name="epl_cos")
        self.rt_fabs = ir.Function(self.module, ir.FunctionType(self.f64, [self.f64]), name="epl_fabs")

        self.rt_file_read = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_file_read")

        # New v3.0 runtime functions
        self.rt_file_write = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr, self.i8_ptr]), name="epl_file_write")
        self.rt_file_append = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr, self.i8_ptr]), name="epl_file_append")
        self.rt_file_exists = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr]), name="epl_file_exists")
        self.rt_file_delete = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr]), name="epl_file_delete")

        self.rt_env_get = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_env_get")
        self.rt_random_int = ir.Function(self.module, ir.FunctionType(self.i64, [self.i64, self.i64]), name="epl_random_int")
        self.rt_random_float = ir.Function(self.module, ir.FunctionType(self.f64, []), name="epl_random_float")
        self.rt_time_now = ir.Function(self.module, ir.FunctionType(self.f64, []), name="epl_time_now")

        self.rt_list_sorted = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_list_sorted")
        self.rt_list_reversed = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_list_reversed")
        self.rt_list_sum = ir.Function(self.module, ir.FunctionType(self.i64, [self.i8_ptr]), name="epl_list_sum")
        self.rt_list_index_of = ir.Function(self.module, ir.FunctionType(self.i64, [self.i8_ptr, self.i64]), name="epl_list_index_of")
        self.rt_list_concat = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr]), name="epl_list_concat")

        self.rt_map_has_key = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr, self.i8_ptr]), name="epl_map_has_key")
        self.rt_map_remove = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr, self.i8_ptr]), name="epl_map_remove")
        self.rt_map_keys = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_map_keys")
        self.rt_map_values = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_map_values")
        self.rt_map_size = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr]), name="epl_map_size")

        self.rt_str_join = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr]), name="epl_string_join")
        self.rt_str_repeat = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i64]), name="epl_string_repeat")
        self.rt_str_index_of = ir.Function(self.module, ir.FunctionType(self.i64, [self.i8_ptr, self.i8_ptr]), name="epl_string_index_of")
        self.rt_str_format = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr]), name="epl_string_format")
        self.rt_char_code = ir.Function(self.module, ir.FunctionType(self.i64, [self.i8_ptr]), name="epl_char_code")
        self.rt_from_char_code = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i64]), name="epl_from_char_code")

        self.rt_type_name = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i32]), name="epl_type_name")

        self.rt_json_list = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_json_serialize_list")
        self.rt_json_map = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_json_serialize_map")

        self.rt_tan = ir.Function(self.module, ir.FunctionType(self.f64, [self.f64]), name="epl_tan")
        self.rt_exp_fn = ir.Function(self.module, ir.FunctionType(self.f64, [self.f64]), name="epl_exp")
        self.rt_log10 = ir.Function(self.module, ir.FunctionType(self.f64, [self.f64]), name="epl_log10")
        self.rt_round = ir.Function(self.module, ir.FunctionType(self.f64, [self.f64]), name="epl_round")
        self.rt_min_int = ir.Function(self.module, ir.FunctionType(self.i64, [self.i64, self.i64]), name="epl_min_int")
        self.rt_max_int = ir.Function(self.module, ir.FunctionType(self.i64, [self.i64, self.i64]), name="epl_max_int")
        self.rt_abs_int = ir.Function(self.module, ir.FunctionType(self.i64, [self.i64]), name="epl_abs_int")
        self.rt_sign = ir.Function(self.module, ir.FunctionType(self.i64, [self.i64]), name="epl_sign")
        self.rt_clamp = ir.Function(self.module, ir.FunctionType(self.i64, [self.i64, self.i64, self.i64]), name="epl_clamp")

        self.rt_system = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr]), name="epl_system")
        self.rt_exit = ir.Function(self.module, ir.FunctionType(self.void, [self.i32]), name="epl_exit")
        self.rt_assert = ir.Function(self.module, ir.FunctionType(self.void, [self.i32, self.i8_ptr]), name="epl_assert")

        # Exception handling (setjmp/longjmp)
        self.rt_try_begin = ir.Function(self.module, ir.FunctionType(self.i32, []), name="epl_try_begin")
        self.rt_try_end = ir.Function(self.module, ir.FunctionType(self.void, []), name="epl_try_end")
        self.rt_throw = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr]), name="epl_throw")
        self.rt_get_exception = ir.Function(self.module, ir.FunctionType(self.i8_ptr, []), name="epl_get_exception")

        # Memory management — free functions
        self.rt_string_free = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr]), name="epl_string_free")
        self.rt_list_free = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr]), name="epl_list_free")
        self.rt_map_free = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr]), name="epl_map_free")
        self.rt_object_free = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr]), name="epl_object_free")

        # Arena allocator
        self.rt_arena_alloc = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i64]), name="epl_arena_alloc")
        self.rt_arena_reset = ir.Function(self.module, ir.FunctionType(self.void, []), name="epl_arena_reset")

        # Closure support
        self.rt_closure_new = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i32]), name="epl_closure_new")
        self.rt_closure_set = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr, self.i32, self.i32, self.i64]), name="epl_closure_set")
        self.rt_closure_get = ir.Function(self.module, ir.FunctionType(self.i64, [self.i8_ptr, self.i32]), name="epl_closure_get")
        self.rt_closure_get_tag = ir.Function(self.module, ir.FunctionType(self.i32, [self.i8_ptr, self.i32]), name="epl_closure_get_tag")
        self.rt_closure_free = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr]), name="epl_closure_free")

        # Class registry / inheritance
        self.rt_class_register = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr]), name="epl_class_register")
        self.rt_class_add_method = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr, self.i8_ptr, self.i8_ptr]), name="epl_class_add_method")
        self.rt_class_lookup_method = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr]), name="epl_class_lookup_method")
        self.rt_object_get_class = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_object_get_class")

        # Reference counting (legacy compat — now no-ops under mark-and-sweep)
        self.rt_rc_retain = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr]), name="epl_rc_retain")
        self.rt_rc_release = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr]), name="epl_rc_release")

        # Mark-and-sweep GC
        self.rt_gc_collect_if_needed = ir.Function(self.module, ir.FunctionType(self.void, []), name="epl_gc_collect_if_needed")
        self.rt_gc_shutdown = ir.Function(self.module, ir.FunctionType(self.void, []), name="epl_gc_shutdown")
        self.rt_gc_root_push = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr]), name="epl_gc_root_push")
        self.rt_gc_root_pop = ir.Function(self.module, ir.FunctionType(self.void, [self.i32]), name="epl_gc_root_pop")
        self.rt_gc_root_pop_to = ir.Function(self.module, ir.FunctionType(self.void, [self.i32]), name="epl_gc_root_pop_to")
        self.rt_gc_root_depth = ir.Function(self.module, ir.FunctionType(self.i32, []), name="epl_gc_root_depth")
        self.rt_gc_new_list = ir.Function(self.module, ir.FunctionType(self.i8_ptr, []), name="epl_gc_new_list")
        self.rt_gc_new_map = ir.Function(self.module, ir.FunctionType(self.i8_ptr, []), name="epl_gc_new_map")
        self.rt_gc_new_object = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_gc_new_object")
        self.rt_gc_new_string = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_gc_new_string")
        self.rt_gc_str_concat = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr]), name="epl_gc_str_concat")
        self.rt_gc_collect = ir.Function(self.module, ir.FunctionType(self.void, []), name="epl_gc_collect")
        self.rt_gc_object_count_fn = ir.Function(self.module, ir.FunctionType(self.i32, []), name="epl_gc_object_count")

        # GC saved-depth variable (set per function scope at runtime)
        self._gc_depth_var = None
        self._loop_gc_depth = None

        # Registries
        self.class_defs = {}
        self.class_props = {}
        self.enum_defs = {}

        # Format strings
        self._fmt_int = self._make_global_string("%lld", "fmt_int")
        self._fmt_float = self._make_global_string("%g", "fmt_float")
        self._fmt_str = self._make_global_string("%s", "fmt_str")
        self._fmt_true = self._make_global_string("true", "fmt_true")
        self._fmt_false = self._make_global_string("false", "fmt_false")
        self._fmt_nothing = self._make_global_string("nothing", "fmt_nothing")
        self._fmt_newline = self._make_global_string("\n", "fmt_newline")
        self._fmt_int_nl = self._make_global_string("%lld\n", "fmt_int_nl")
        self._fmt_float_nl = self._make_global_string("%g\n", "fmt_float_nl")
        self._fmt_str_nl = self._make_global_string("%s\n", "fmt_str_nl")

        # v5.2 Phase 1: Threading runtime
        self.rt_spawn_task = ir.Function(self.module, ir.FunctionType(self.i64, [self.i8_ptr]), name="epl_spawn_task")
        self.rt_spawn_wait = ir.Function(self.module, ir.FunctionType(self.void, [self.i64]), name="epl_spawn_wait")
        self.rt_spawn_wait_all = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr, self.i32]), name="epl_spawn_wait_all")
        self.rt_sleep_ms = ir.Function(self.module, ir.FunctionType(self.void, [self.i32]), name="epl_sleep_ms")

        # v5.2 Phase 1: Dynamic library loading (FFI)
        self.rt_dlopen = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr]), name="epl_dlopen")
        self.rt_dlsym = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr]), name="epl_dlsym")
        self.rt_dlclose = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr]), name="epl_dlclose")
        self.rt_ffi_call_i64 = ir.Function(self.module, ir.FunctionType(self.i64, [self.i8_ptr, self.i8_ptr, self.i32]), name="epl_ffi_call_i64")
        self.rt_ffi_call_double = ir.Function(self.module, ir.FunctionType(self.f64, [self.i8_ptr, self.i8_ptr, self.i32]), name="epl_ffi_call_double")
        self.rt_ffi_call_ptr = ir.Function(self.module, ir.FunctionType(self.i8_ptr, [self.i8_ptr, self.i8_ptr, self.i32]), name="epl_ffi_call_ptr")
        self.rt_ffi_call_void = ir.Function(self.module, ir.FunctionType(self.void, [self.i8_ptr, self.i8_ptr, self.i32]), name="epl_ffi_call_void")

        # v5.2 Phase 1: Debug trap
        self.rt_debug_trap = ir.Function(self.module, ir.FunctionType(self.void, []), name="epl_debug_trap")

        # v5.2 Phase 1: Spawn trampoline counter
        self._spawn_counter = 0
        # Library handle cache: library_path -> variable name
        self._lib_handles = {}

    def _make_global_string(self, text, name):
        if name in self.string_constants:
            return self.string_constants[name]
        encoded = bytearray(text.encode('utf-8')) + bytearray([0])
        str_type = ir.ArrayType(self.i8, len(encoded))
        global_str = ir.GlobalVariable(self.module, str_type, name=name)
        global_str.global_constant = True
        global_str.linkage = 'private'
        global_str.initializer = ir.Constant(str_type, encoded)
        self.string_constants[name] = global_str
        return global_str

    def _get_string_ptr(self, global_str):
        return self.builder.bitcast(global_str, self.i8_ptr)

    # ─── Entry Points ────────────────────────────────────

    def compile(self, program: ast.Program):
        # Initialize DWARF debug info if requested
        if self.debug:
            self._init_debug_info()

        main_ty = ir.FunctionType(self.i32, [])
        main_fn = ir.Function(self.module, main_ty, name="main")
        block = main_fn.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(block)
        self.func = main_fn
        self.variables = {}

        if self.debug:
            self._attach_debug_to_function(main_fn, 'main', 1)
            self._set_debug_loc(1)
        # Save GC root stack depth at main entry
        self._gc_depth_var = self._gc_save_depth()

        for stmt in program.statements:
            if isinstance(stmt, ast.FunctionDef):
                self._register_function(stmt)
            elif isinstance(stmt, ast.AsyncFunctionDef):
                sync = ast.FunctionDef(stmt.name, stmt.params, stmt.return_type, stmt.body, stmt.line)
                self._register_function(sync)
            elif isinstance(stmt, ast.ClassDef):
                self._compile_class_def(stmt)
            elif isinstance(stmt, ast.EnumDef):
                self._compile_enum_def(stmt)
            elif isinstance(stmt, ast.ModuleDef):
                # Pre-register module functions
                for item in stmt.body:
                    if isinstance(item, ast.FunctionDef):
                        prefixed = ast.FunctionDef(
                            f"{stmt.name}_{item.name}", item.params,
                            item.return_type, item.body, item.line
                        )
                        self._register_function(prefixed)
            elif isinstance(stmt, ast.InterfaceDefNode):
                pass  # Interfaces are type-check-only
            elif isinstance(stmt, ast.VisibilityModifier):
                inner = stmt.statement
                if isinstance(inner, ast.FunctionDef):
                    self._register_function(inner)
                elif isinstance(inner, ast.ClassDef):
                    self._compile_class_def(inner)

        for stmt in program.statements:
            if stmt is not None:
                if self.builder.block.is_terminated:
                    break
                if self.debug:
                    line = getattr(stmt, 'line', 0)
                    if line:
                        self._set_debug_loc(line)
                self._compile_stmt(stmt)

        if not self.builder.block.is_terminated:
            # GC: shut down collector (frees all tracked objects + arena)
            self.builder.call(self.rt_gc_shutdown, [])
            self.builder.ret(ir.Constant(self.i32, 0))
        return str(self.module)

    def compile_to_object(self, ir_string=None):
        if ir_string is None:
            ir_string = str(self.module)
        mod = llvm.parse_assembly(ir_string)
        mod.verify()

        target = llvm.Target.from_default_triple()
        tm = target.create_target_machine(
            opt=self.opt_level, reloc='pic', codemodel='default')

        # Apply LLVM optimization passes via the new pass manager
        if self.opt_level > 0:
            pto = llvm.PipelineTuningOptions()
            pto.speed_level = self.opt_level
            pto.size_level = 0  # optimize for speed, not size
            pto.loop_vectorization = self.opt_level >= 2
            pto.slp_vectorization = self.opt_level >= 2
            pto.loop_unrolling = self.opt_level >= 2
            pto.loop_interleaving = self.opt_level >= 2
            # Aggressive inlining at O3
            if self.opt_level >= 3:
                pto.inlining_threshold = 275  # higher threshold = more inlining
            pb = llvm.create_pass_builder(tm, pto)
            mpm = pb.getModulePassManager()
            mpm.run(mod, pb)
            pb.close()

        return tm.emit_object(mod)

    def compile_to_executable(self, program, output_path="output", runtime_c=None):
        """Full pipeline: EPL AST -> LLVM IR -> object file -> linked executable.
        
        Args:
            program: AST Program node
            output_path: Path for the output executable (no extension)
            runtime_c: Path to runtime.c (auto-detected if None)
        """
        import subprocess
        import tempfile
        import os
        
        # Step 1: Generate IR
        ir_code = self.compile(program)
        
        # Step 2: Compile to object file
        obj_bytes = self.compile_to_object(ir_code)
        
        # Step 3: Write object file
        obj_path = output_path + '.o'
        with open(obj_path, 'wb') as f:
            f.write(obj_bytes)
        
        # Step 4: Find runtime.c
        if runtime_c is None:
            # Look for runtime.c in common locations
            candidates = [
                os.path.join(os.path.dirname(__file__), 'runtime.c'),
                os.path.join(os.getcwd(), 'epl', 'runtime.c'),
                os.path.join(os.getcwd(), 'runtime.c'),
            ]
            for c in candidates:
                if os.path.exists(c):
                    runtime_c = c
                    break
        
        if runtime_c is None or not os.path.exists(runtime_c):
            raise FileNotFoundError("runtime.c not found. Provide path via runtime_c parameter.")
        
        # Step 5: Compile runtime.c to object
        rt_obj = output_path + '_rt.o'
        c_opt_flag = f'-O{self.opt_level}'
        try:
            subprocess.run(['gcc', '-c', c_opt_flag, '-o', rt_obj, runtime_c], 
                          check=True, capture_output=True, text=True)
        except FileNotFoundError:
            try:
                subprocess.run(['clang', '-c', c_opt_flag, '-o', rt_obj, runtime_c],
                              check=True, capture_output=True, text=True)
            except FileNotFoundError:
                raise RuntimeError("C compiler (gcc or clang) not found. Install gcc or clang to compile.")
        
        # Step 6: Link
        exe_path = output_path + ('.exe' if os.name == 'nt' else '')
        try:
            subprocess.run(['gcc', '-o', exe_path, obj_path, rt_obj, '-lm'],
                          check=True, capture_output=True, text=True)
        except FileNotFoundError:
            subprocess.run(['clang', '-o', exe_path, obj_path, rt_obj, '-lm'],
                          check=True, capture_output=True, text=True)
        
        # Clean up intermediate files
        for f in [obj_path, rt_obj]:
            try:
                os.remove(f)
            except OSError:
                pass
        
        return exe_path

    def compile_to_wasm(self, program, output_path="output", runtime_c=None):
        """Compile EPL to WebAssembly via emcc or clang --target=wasm32-wasi.
        
        Generates LLVM IR with wasm32 target triple, writes it to a .ll file,
        then invokes an external WASM-capable compiler (emcc preferred,
        clang --target=wasm32-wasi fallback).
        
        Args:
            program: AST Program node
            output_path: Base path for output files (no extension)
            runtime_c: Path to runtime.c (auto-detected if None)
            
        Returns:
            Path to the generated .wasm file
        """
        import subprocess
        import os

        # Step 1: Set WASM target triple before compiling
        saved_triple = self.module.triple
        saved_layout = self.module.data_layout
        self.module.triple = 'wasm32-unknown-wasi'
        self.module.data_layout = 'e-m:e-p:32:32-i64:64-n32:64-S128'

        try:
            ir_code = self.compile(program)
        finally:
            # Restore original triple for potential reuse
            self.module.triple = saved_triple
            self.module.data_layout = saved_layout

        # Step 2: Write IR to file
        ll_path = output_path + '.ll'
        with open(ll_path, 'w', encoding='utf-8') as f:
            f.write(ir_code)

        # Step 3: Find runtime.c
        if runtime_c is None:
            candidates = [
                os.path.join(os.path.dirname(__file__), 'runtime.c'),
                os.path.join(os.getcwd(), 'epl', 'runtime.c'),
                os.path.join(os.getcwd(), 'runtime.c'),
            ]
            for c in candidates:
                if os.path.exists(c):
                    runtime_c = c
                    break

        wasm_path = output_path + '.wasm'
        c_opt_flag = f'-O{self.opt_level}'

        # Step 4: Try emcc (Emscripten) first
        try:
            cmd = ['emcc', ll_path, '-o', wasm_path, c_opt_flag,
                   '-s', 'STANDALONE_WASM=1', '-s', 'WASM=1',
                   '-s', 'EXPORTED_FUNCTIONS=["_main"]']
            if runtime_c and os.path.exists(runtime_c):
                cmd.insert(2, runtime_c)
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
            self._cleanup_files([ll_path])
            return wasm_path
        except FileNotFoundError:
            pass
        except subprocess.CalledProcessError as e:
            # emcc found but compilation failed — try clang next
            emcc_err = e.stderr[:500] if e.stderr else ''
            pass
        except subprocess.TimeoutExpired:
            pass

        # Step 5: Try clang --target=wasm32-wasi
        try:
            cmd = ['clang', '--target=wasm32-wasi', ll_path, '-o', wasm_path,
                   c_opt_flag, '-nostdlib',
                   '-Wl,--export=main', '-Wl,--export-all']
            if runtime_c and os.path.exists(runtime_c):
                cmd.insert(3, runtime_c)
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
            self._cleanup_files([ll_path])
            return wasm_path
        except FileNotFoundError:
            pass
        except subprocess.CalledProcessError as e:
            clang_err = e.stderr[:500] if e.stderr else ''
            raise RuntimeError(
                f"WASM compilation failed.\n"
                f"  clang error: {clang_err}\n"
                f"  LLVM IR saved to: {ll_path}"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"WASM compilation timed out after 120 seconds.\n"
                f"  LLVM IR saved to: {ll_path}"
            )

        raise RuntimeError(
            "No WASM compiler found. Install Emscripten (emcc) or clang with WASM target.\n"
            "  Install Emscripten: https://emscripten.org/docs/getting_started/downloads.html\n"
            f"  LLVM IR saved to: {ll_path}"
        )

    @staticmethod
    def _cleanup_files(paths):
        """Remove temporary files, ignoring errors."""
        import os
        for p in paths:
            try:
                os.remove(p)
            except OSError:
                pass

    def get_ir(self, program: ast.Program):
        return self.compile(program)

    # ─── Type Coercion ────────────────────────────────────

    def _coerce_to_type(self, value, target_type):
        """Coerce an LLVM value to a target type for function calls."""
        if value.type == target_type:
            return value
        # int -> pointer
        if isinstance(value.type, ir.IntType) and isinstance(target_type, ir.PointerType):
            return self.builder.inttoptr(value, target_type)
        # pointer -> int
        if isinstance(value.type, ir.PointerType) and isinstance(target_type, ir.IntType):
            return self.builder.ptrtoint(value, target_type)
        # float -> int
        if isinstance(value.type, ir.DoubleType) and isinstance(target_type, ir.IntType):
            return self.builder.fptosi(value, target_type)
        # int -> float
        if isinstance(value.type, ir.IntType) and isinstance(target_type, ir.DoubleType):
            return self.builder.sitofp(value, target_type)
        # float -> pointer (through int)
        if isinstance(value.type, ir.DoubleType) and isinstance(target_type, ir.PointerType):
            vi = self.builder.bitcast(value, self.i64)
            return self.builder.inttoptr(vi, target_type)
        # pointer -> float (through int)
        if isinstance(value.type, ir.PointerType) and isinstance(target_type, ir.DoubleType):
            vi = self.builder.ptrtoint(value, self.i64)
            return self.builder.bitcast(vi, target_type)
        # int width mismatch
        if isinstance(value.type, ir.IntType) and isinstance(target_type, ir.IntType):
            if value.type.width < target_type.width:
                return self.builder.sext(value, target_type)
            elif value.type.width > target_type.width:
                return self.builder.trunc(value, target_type)
        # pointer type mismatch
        if isinstance(value.type, ir.PointerType) and isinstance(target_type, ir.PointerType):
            return self.builder.bitcast(value, target_type)
        return value

    # ─── GC Helpers ──────────────────────────────────────

    def _gc_push_root(self, ptr):
        """Push a heap pointer onto the GC shadow-stack so it is reachable during collection."""
        if isinstance(ptr.type, ir.PointerType):
            self.builder.call(self.rt_gc_root_push, [ptr])
        else:
            # Cast non-pointer (e.g. i64 holding a ptr) to i8*
            self.builder.call(self.rt_gc_root_push, [self.builder.inttoptr(ptr, self.i8_ptr)])

    def _gc_save_depth(self):
        """Save the current GC root stack depth into a local variable.
        Returns the alloca holding the saved depth."""
        depth_var = self.builder.alloca(self.i32, name="gc_saved_depth")
        cur_depth = self.builder.call(self.rt_gc_root_depth, [])
        self.builder.store(cur_depth, depth_var)
        return depth_var

    def _gc_restore_depth(self, depth_var):
        """Restore the GC root stack to a previously saved depth."""
        saved = self.builder.load(depth_var)
        self.builder.call(self.rt_gc_root_pop_to, [saved])

    def _gc_safepoint(self):
        """Insert a GC collection check (at loop headers, long functions)."""
        self.builder.call(self.rt_gc_collect_if_needed, [])

    def _check_div_by_zero(self, divisor):
        """Emit a runtime check that aborts with an error on integer division by zero."""
        if not isinstance(divisor.type, ir.IntType):
            return  # float division by zero is defined (produces inf/nan)
        is_zero = self.builder.icmp_signed('==', divisor, ir.Constant(divisor.type, 0))
        fn = self.builder.function
        err_bb = fn.append_basic_block('div_by_zero')
        ok_bb = fn.append_basic_block('div_ok')
        self.builder.cbranch(is_zero, err_bb, ok_bb)
        self.builder.position_at_start(err_bb)
        msg = self._get_string_ptr(self._make_global_string("Error: Division by zero\n", "err_div_zero"))
        self.builder.call(self.printf, [msg])
        self.builder.call(self.exit_fn, [ir.Constant(self.i32, 1)])
        self.builder.unreachable()
        self.builder.position_at_start(ok_bb)

    # ─── Statement Dispatch ──────────────────────────────

    def _compile_stmt(self, node):
        if self.debug:
            line = getattr(node, 'line', 0)
            if line:
                self._set_debug_loc(line)
        if isinstance(node, ast.VarDeclaration): return self._compile_var_decl(node)
        if isinstance(node, ast.VarAssignment): return self._compile_var_assign(node)
        if isinstance(node, ast.PrintStatement): return self._compile_print(node)
        if isinstance(node, ast.InputStatement): return self._compile_input(node)
        if isinstance(node, ast.IfStatement): return self._compile_if(node)
        if isinstance(node, ast.WhileLoop): return self._compile_while(node)
        if isinstance(node, ast.RepeatLoop): return self._compile_repeat(node)
        if isinstance(node, ast.ForRange): return self._compile_for_range(node)
        if isinstance(node, ast.ForEachLoop): return self._compile_for_each(node)
        if isinstance(node, ast.FunctionDef): return self._compile_function_def(node)
        if isinstance(node, ast.FunctionCall): return self._compile_function_call(node)
        if isinstance(node, ast.ReturnStatement): return self._compile_return(node)
        if isinstance(node, ast.BreakStatement): return self._compile_break(node)
        if isinstance(node, ast.ContinueStatement): return self._compile_continue(node)
        if isinstance(node, ast.MatchStatement): return self._compile_match(node)
        if isinstance(node, ast.ConstDeclaration): return self._compile_const(node)
        if isinstance(node, ast.AssertStatement): return self._compile_assert(node)
        if isinstance(node, ast.ExitStatement): return self._compile_exit(node)
        if isinstance(node, ast.WaitStatement): return self._compile_wait(node)
        if isinstance(node, ast.MethodCall): return self._compile_method_call_stmt(node)
        if isinstance(node, ast.PropertySet): return self._compile_property_set(node)
        if isinstance(node, ast.IndexSet): return self._compile_index_set(node)
        if isinstance(node, ast.TryCatch): return self._compile_try_catch(node)
        if isinstance(node, ast.ClassDef): return
        if isinstance(node, ast.EnumDef): return
        if isinstance(node, ast.FileWrite): return self._compile_file_write(node)
        if isinstance(node, ast.FileAppend): return self._compile_file_append(node)
        if isinstance(node, ast.ImportStatement): return self._compile_import(node)
        if isinstance(node, ast.AugmentedAssignment): return self._compile_augmented_assign(node)
        if isinstance(node, ast.ThrowStatement): return self._compile_throw(node)
        if isinstance(node, ast.UseStatement): return
        # v4.0: Production-level nodes
        if isinstance(node, ast.TryCatchFinally): return self._compile_try_catch_finally(node)
        if isinstance(node, ast.AsyncFunctionDef): return self._compile_async_function(node)
        if isinstance(node, ast.SuperCall): return self._compile_super_call(node)
        if isinstance(node, ast.InterfaceDefNode): return  # Interface is type-check-only, no codegen
        if isinstance(node, ast.ModuleDef): return self._compile_module_def(node)
        if isinstance(node, ast.ModuleAccess): return self._compile_module_access(node)
        if isinstance(node, ast.ExportStatement): return  # Export is namespace metadata, no codegen
        if isinstance(node, ast.VisibilityModifier): return self._compile_stmt(node.statement)
        if isinstance(node, ast.GenericClassDef): return  # Type-erased: treated same as ClassDef, registered in pre-pass
        if isinstance(node, ast.SpawnStatement): return self._compile_spawn(node)
        if isinstance(node, ast.ParallelForEach): return self._compile_parallel_for_each(node)
        if isinstance(node, ast.BreakpointStatement): return self._compile_breakpoint(node)
        if isinstance(node, ast.ExternalFunctionDef): return self._compile_external_function_def(node)
        if isinstance(node, ast.LoadLibrary): return self._compile_load_library(node)
        if isinstance(node, ast.StaticMethodDef): return  # Compiled in class context
        if isinstance(node, ast.AbstractMethodDef): return  # No body, nothing to compile
        if isinstance(node, ast.YieldStatement): return self._compile_yield(node)
        if isinstance(node, ast.DestructureAssignment): return self._compile_destructure(node)
        # Unknown statement — emit a warning and skip
        _warnings.warn(f"Compiler: skipping unsupported statement {type(node).__name__}", stacklevel=2)

    # ─── Variables ────────────────────────────────────────

    def _compile_var_decl(self, node):
        value = self._compile_expr(node.value)
        if isinstance(node.value, ast.ListLiteral): self.var_types[node.name] = 'list'
        elif isinstance(node.value, ast.DictLiteral): self.var_types[node.name] = 'map'
        elif isinstance(node.value, ast.NewInstance): self.var_types[node.name] = 'object'
        elif isinstance(value.type, ir.PointerType): self.var_types[node.name] = 'string'
        elif isinstance(value.type, ir.DoubleType): self.var_types[node.name] = 'float'
        else: self.var_types[node.name] = 'int'
        if node.name not in self.variables:
            alloca = self.builder.alloca(value.type, name=_mangle_name(node.name))
            self.variables[node.name] = alloca
        self.builder.store(value, self.variables[node.name])

    def _compile_var_assign(self, node):
        value = self._compile_expr(node.value)
        if node.name not in self.variables:
            alloca = self.builder.alloca(value.type, name=_mangle_name(node.name))
            self.variables[node.name] = alloca
        self.builder.store(value, self.variables[node.name])

    def _compile_const(self, node):
        self._compile_var_decl(ast.VarDeclaration(node.name, node.value, None, node.line))

    # ─── Augmented Assignment ─────────────────────────────

    def _compile_augmented_assign(self, node):
        if node.name not in self.variables:
            raise EPLRuntimeError(f'Variable "{node.name}" not defined.', node.line)
        cur = self.builder.load(self.variables[node.name])
        rhs = self._compile_expr(node.value)

        if isinstance(cur.type, ir.PointerType) and isinstance(rhs.type, ir.PointerType) and node.operator == '+=':
            result = self._compile_str_concat(cur, rhs)
            self.builder.store(result, self.variables[node.name])
            return

        if self.var_types.get(node.name) == 'list' and node.operator == '+=':
            tag = ir.Constant(self.i32, TAG_INT) if isinstance(rhs.type, ir.IntType) else ir.Constant(self.i32, TAG_STRING)
            val = rhs if isinstance(rhs.type, ir.IntType) and rhs.type.width == 64 else (
                self.builder.ptrtoint(rhs, self.i64) if isinstance(rhs.type, ir.PointerType) else self.builder.sext(rhs, self.i64))
            self.builder.call(self.rt_list_push, [cur, tag, val])
            return

        if isinstance(cur.type, ir.DoubleType) or isinstance(rhs.type, ir.DoubleType):
            if isinstance(cur.type, ir.IntType): cur = self.builder.sitofp(cur, self.f64)
            if isinstance(rhs.type, ir.IntType): rhs = self.builder.sitofp(rhs, self.f64)
            ops = {'+=': 'fadd', '-=': 'fsub', '*=': 'fmul', '/=': 'fdiv', '%=': 'frem'}
            result = getattr(self.builder, ops.get(node.operator, 'fadd'))(cur, rhs)
        else:
            if isinstance(cur.type, ir.IntType) and isinstance(rhs.type, ir.IntType):
                if cur.type.width < rhs.type.width: cur = self.builder.sext(cur, rhs.type)
                elif rhs.type.width < cur.type.width: rhs = self.builder.sext(rhs, cur.type)
            ops = {'+=': 'add', '-=': 'sub', '*=': 'mul', '/=': 'sdiv', '%=': 'srem'}
            if node.operator in ('/=', '%='):
                self._check_div_by_zero(rhs)
            result = getattr(self.builder, ops.get(node.operator, 'add'))(cur, rhs)
        self.builder.store(result, self.variables[node.name])

    # ─── Print ────────────────────────────────────────────

    def _compile_print(self, node):
        value = self._compile_expr(node.expression)
        if isinstance(node.expression, ast.Identifier) and self.var_types.get(node.expression.name) == 'list':
            self.builder.call(self.rt_list_print, [value])
            return
        if isinstance(value.type, ir.IntType) and value.type.width == 64:
            self.builder.call(self.printf, [self._get_string_ptr(self._fmt_int_nl), value])
        elif isinstance(value.type, ir.DoubleType):
            self.builder.call(self.printf, [self._get_string_ptr(self._fmt_float_nl), value])
        elif isinstance(value.type, ir.PointerType):
            self.builder.call(self.printf, [self._get_string_ptr(self._fmt_str_nl), value])
        elif isinstance(value.type, ir.IntType) and value.type.width == 1:
            t = self._get_string_ptr(self._fmt_true)
            f = self._get_string_ptr(self._fmt_false)
            s = self.builder.select(value, t, f)
            self.builder.call(self.printf, [self._get_string_ptr(self._fmt_str_nl), s])
        else:
            self.builder.call(self.printf, [self._get_string_ptr(self._fmt_int_nl), value])

    # ─── Input ────────────────────────────────────────────

    def _compile_input(self, node):
        if node.prompt:
            prompt = self._compile_expr(node.prompt)
            result = self.builder.call(self.rt_input, [prompt])
        else:
            result = self.builder.call(self.rt_input_no, [])
        if node.variable_name not in self.variables:
            alloca = self.builder.alloca(self.i8_ptr, name=node.variable_name)
            self.variables[node.variable_name] = alloca
            self.var_types[node.variable_name] = 'string'
        self.builder.store(result, self.variables[node.variable_name])

    # ─── Control Flow ────────────────────────────────────

    def _to_bool(self, v):
        if isinstance(v.type, ir.IntType) and v.type.width == 1: return v
        if isinstance(v.type, ir.IntType): return self.builder.icmp_signed('!=', v, ir.Constant(v.type, 0))
        if isinstance(v.type, ir.DoubleType): return self.builder.fcmp_ordered('!=', v, ir.Constant(self.f64, 0.0))
        if isinstance(v.type, ir.PointerType):
            return self.builder.icmp_signed('!=', self.builder.ptrtoint(v, self.i64), ir.Constant(self.i64, 0))
        return ir.Constant(self.i1, 1)

    def _compile_if(self, node):
        cond = self._to_bool(self._compile_expr(node.condition))
        then_bb = self.func.append_basic_block('then')
        else_bb = self.func.append_basic_block('else')
        merge_bb = self.func.append_basic_block('merge')
        self.builder.cbranch(cond, then_bb, else_bb)
        self.builder.position_at_start(then_bb)
        for s in node.then_body:
            if s: self._compile_stmt(s)
        if not self.builder.block.is_terminated: self.builder.branch(merge_bb)
        self.builder.position_at_start(else_bb)
        if node.else_body:
            for s in node.else_body:
                if s: self._compile_stmt(s)
        if not self.builder.block.is_terminated: self.builder.branch(merge_bb)
        self.builder.position_at_start(merge_bb)

    def _compile_while(self, node):
        cond_bb = self.func.append_basic_block('while_cond')
        body_bb = self.func.append_basic_block('while_body')
        end_bb = self.func.append_basic_block('while_end')
        ob, oc = self.break_block, self.continue_block
        old_loop_gc = self._loop_gc_depth
        self.break_block, self.continue_block = end_bb, cond_bb
        # Save GC depth before loop so roots from each iteration are cleaned up
        loop_gc_depth = self._gc_save_depth()
        self._loop_gc_depth = loop_gc_depth
        self.builder.branch(cond_bb)
        self.builder.position_at_start(cond_bb)
        self._gc_restore_depth(loop_gc_depth)
        self._gc_safepoint()
        self.builder.cbranch(self._to_bool(self._compile_expr(node.condition)), body_bb, end_bb)
        self.builder.position_at_start(body_bb)
        for s in node.body:
            if s: self._compile_stmt(s)
        if not self.builder.block.is_terminated: self.builder.branch(cond_bb)
        self.builder.position_at_start(end_bb)
        self._gc_restore_depth(loop_gc_depth)
        self.break_block, self.continue_block = ob, oc
        self._loop_gc_depth = old_loop_gc

    def _compile_repeat(self, node):
        count = self._compile_expr(node.count)
        ctr = self.builder.alloca(self.i64, name="rep_ctr")
        self.builder.store(ir.Constant(self.i64, 0), ctr)
        cond_bb = self.func.append_basic_block('rep_cond')
        body_bb = self.func.append_basic_block('rep_body')
        end_bb = self.func.append_basic_block('rep_end')
        ob, oc = self.break_block, self.continue_block
        old_loop_gc = self._loop_gc_depth
        self.break_block, self.continue_block = end_bb, cond_bb
        loop_gc_depth = self._gc_save_depth()
        self._loop_gc_depth = loop_gc_depth
        self.builder.branch(cond_bb)
        self.builder.position_at_start(cond_bb)
        self._gc_restore_depth(loop_gc_depth)
        self._gc_safepoint()
        self.builder.cbranch(self.builder.icmp_signed('<', self.builder.load(ctr), count), body_bb, end_bb)
        self.builder.position_at_start(body_bb)
        for s in node.body:
            if s: self._compile_stmt(s)
        if not self.builder.block.is_terminated:
            c = self.builder.load(ctr)
            self.builder.store(self.builder.add(c, ir.Constant(self.i64, 1)), ctr)
            self.builder.branch(cond_bb)
        self.builder.position_at_start(end_bb)
        self._gc_restore_depth(loop_gc_depth)
        self.break_block, self.continue_block = ob, oc
        self._loop_gc_depth = old_loop_gc

    def _compile_for_range(self, node):
        start = self._compile_expr(node.start)
        end = self._compile_expr(node.end)
        step = self._compile_expr(node.step) if node.step else ir.Constant(self.i64, 1)
        if node.var_name not in self.variables:
            a = self.builder.alloca(self.i64, name=node.var_name)
            self.variables[node.var_name] = a
            self.var_types[node.var_name] = 'int'
        self.builder.store(start, self.variables[node.var_name])

        cond_bb = self.func.append_basic_block('for_cond')
        body_bb = self.func.append_basic_block('for_body')
        inc_bb = self.func.append_basic_block('for_inc')
        end_bb = self.func.append_basic_block('for_end')
        ob, oc = self.break_block, self.continue_block
        old_loop_gc = self._loop_gc_depth
        self.break_block, self.continue_block = end_bb, inc_bb
        loop_gc_depth = self._gc_save_depth()
        self._loop_gc_depth = loop_gc_depth
        self.builder.branch(cond_bb)

        self.builder.position_at_start(cond_bb)
        self._gc_restore_depth(loop_gc_depth)
        self._gc_safepoint()
        cur = self.builder.load(self.variables[node.var_name])
        # Detect negative step
        is_neg_step = isinstance(node.step, ast.UnaryOp) and node.step.operator == '-'
        if is_neg_step:
            cond = self.builder.icmp_signed('>=', cur, end)
        else:
            cond = self.builder.icmp_signed('<=', cur, end)
        self.builder.cbranch(cond, body_bb, end_bb)

        self.builder.position_at_start(body_bb)
        for s in node.body:
            if s: self._compile_stmt(s)
        if not self.builder.block.is_terminated: self.builder.branch(inc_bb)

        self.builder.position_at_start(inc_bb)
        cur = self.builder.load(self.variables[node.var_name])
        self.builder.store(self.builder.add(cur, step), self.variables[node.var_name])
        self.builder.branch(cond_bb)

        self.builder.position_at_start(end_bb)
        self._gc_restore_depth(loop_gc_depth)
        self.break_block, self.continue_block = ob, oc
        self._loop_gc_depth = old_loop_gc

    def _compile_for_each(self, node):
        iterable = self._compile_expr(node.iterable)
        is_list = isinstance(node.iterable, ast.Identifier) and self.var_types.get(node.iterable.name) == 'list'

        ctr = self.builder.alloca(self.i64, name="fe_idx")
        self.builder.store(ir.Constant(self.i64, 0), ctr)

        if is_list:
            length = self.builder.sext(self.builder.call(self.rt_list_length, [iterable]), self.i64)
        else:
            length = self.builder.call(self.rt_str_length, [iterable])

        cond_bb = self.func.append_basic_block('fe_cond')
        body_bb = self.func.append_basic_block('fe_body')
        inc_bb = self.func.append_basic_block('fe_inc')
        end_bb = self.func.append_basic_block('fe_end')
        ob, oc = self.break_block, self.continue_block
        old_loop_gc = self._loop_gc_depth
        self.break_block, self.continue_block = end_bb, inc_bb
        loop_gc_depth = self._gc_save_depth()
        self._loop_gc_depth = loop_gc_depth
        self.builder.branch(cond_bb)

        self.builder.position_at_start(cond_bb)
        self._gc_restore_depth(loop_gc_depth)
        self._gc_safepoint()
        idx = self.builder.load(ctr)
        self.builder.cbranch(self.builder.icmp_signed('<', idx, length), body_bb, end_bb)

        self.builder.position_at_start(body_bb)
        idx = self.builder.load(ctr)
        if is_list:
            elem = self.builder.call(self.rt_list_get_int, [iterable, idx])
            if node.var_name not in self.variables:
                a = self.builder.alloca(self.i64, name=node.var_name)
                self.variables[node.var_name] = a
                self.var_types[node.var_name] = 'int'
            self.builder.store(elem, self.variables[node.var_name])
        else:
            ch = self.builder.call(self.rt_str_index, [iterable, idx])
            if node.var_name not in self.variables:
                a = self.builder.alloca(self.i8_ptr, name=node.var_name)
                self.variables[node.var_name] = a
                self.var_types[node.var_name] = 'string'
            self.builder.store(ch, self.variables[node.var_name])

        for s in node.body:
            if s: self._compile_stmt(s)
        if not self.builder.block.is_terminated: self.builder.branch(inc_bb)

        self.builder.position_at_start(inc_bb)
        idx = self.builder.load(ctr)
        self.builder.store(self.builder.add(idx, ir.Constant(self.i64, 1)), ctr)
        self.builder.branch(cond_bb)

        self.builder.position_at_start(end_bb)
        self._gc_restore_depth(loop_gc_depth)
        self.break_block, self.continue_block = ob, oc
        self._loop_gc_depth = old_loop_gc

    # ─── Functions ────────────────────────────────────────

    def _infer_param_type(self, param):
        """Infer LLVM type from EPL type annotation."""
        ptype = param[1] if len(param) > 1 else None
        if ptype in ('integer', 'int', 'number'):
            return self.i64, 'int'
        elif ptype in ('decimal', 'float', 'double'):
            return self.f64, 'float'
        elif ptype in ('text', 'string', 'str'):
            return self.i8_ptr, 'string'
        elif ptype in ('boolean', 'bool'):
            return self.i1, 'int'
        elif ptype in ('list', 'array'):
            return self.i8_ptr, 'list'
        elif ptype in ('map', 'dict', 'dictionary'):
            return self.i8_ptr, 'map'
        # Default: use i8* (generic pointer) for untyped params
        return self.i8_ptr, 'string'

    def _register_function(self, node):
        """Register a function with improved type inference from annotations."""
        param_types = []
        param_epl_types = []
        for param in node.params:
            llvm_type, epl_type = self._infer_param_type(param)
            param_types.append(llvm_type)
            param_epl_types.append(epl_type)
        
        # Return type: default to i8* (generic), but store info for later
        ret_type = self.i8_ptr
        ret_epl = 'string'
        if hasattr(node, 'return_type') and node.return_type:
            rt = node.return_type
            if rt in ('integer', 'int', 'number'):
                ret_type, ret_epl = self.i64, 'int'
            elif rt in ('decimal', 'float', 'double'):
                ret_type, ret_epl = self.f64, 'float'
            elif rt in ('boolean', 'bool'):
                ret_type, ret_epl = self.i1, 'int'
                
        func_ty = ir.FunctionType(ret_type, param_types)
        func = ir.Function(self.module, func_ty, name=f"epl_{_mangle_name(node.name)}")
        self.functions[node.name] = (func, node, param_epl_types, ret_epl)

    def _compile_function_def(self, node):
        if node.name not in self.functions:
            self._register_function(node)
        func_info = self.functions[node.name]
        func = func_info[0]
        param_epl_types = func_info[2] if len(func_info) > 2 else ['string'] * len(node.params)
        
        ob, of, ov, ot = self.builder, self.func, self.variables.copy(), self.var_types.copy()
        saved_gc_depth_var = self._gc_depth_var
        saved_loop_gc_depth = self._loop_gc_depth
        saved_di_subprogram = self._di_subprogram
        self._loop_gc_depth = None
        block = func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(block)
        self.func = func

        if self.debug:
            line = getattr(node, 'line', 0) or 1
            self._attach_debug_to_function(func, node.name, line)
            self._set_debug_loc(line)

        self.variables = {}
        # Save GC root stack depth at function entry (runtime value)
        self._gc_depth_var = self._gc_save_depth()
        for i, param in enumerate(node.params):
            pn = param[0]
            ptype = func.args[i].type
            a = self.builder.alloca(ptype, name=pn)
            self.builder.store(func.args[i], a)
            self.variables[pn] = a
            self.var_types[pn] = param_epl_types[i] if i < len(param_epl_types) else 'string'
            
            # Handle default values
            if len(param) > 2 and param[2] is not None:
                # Default value exists - won't be used at LLVM level (handled at call site)
                pass
                
        for s in node.body:
            if s: self._compile_stmt(s)
        if not self.builder.block.is_terminated:
            # Restore GC root stack to saved depth
            self._gc_restore_depth(self._gc_depth_var)
            # Return proper type
            ret_type = func.return_value.type
            if isinstance(ret_type, ir.PointerType):
                self.builder.ret(ir.Constant(self.i8_ptr, None))
            elif isinstance(ret_type, ir.IntType) and ret_type.width == 64:
                self.builder.ret(ir.Constant(self.i64, 0))
            elif isinstance(ret_type, ir.DoubleType):
                self.builder.ret(ir.Constant(self.f64, 0.0))
            else:
                self.builder.ret(ir.Constant(self.i8_ptr, None))
        self._gc_depth_var = saved_gc_depth_var
        self._loop_gc_depth = saved_loop_gc_depth
        self._di_subprogram = saved_di_subprogram
        self.builder, self.func, self.variables, self.var_types = ob, of, ov, ot

    def _compile_function_call(self, node):
        builtins = {'length','type_of','typeof','to_integer','to_text','to_decimal','to_boolean',
                     'absolute','round','max','min','random','uppercase','lowercase','sqrt',
                     'power','floor','ceil','log','sin','cos','range','sum','sorted','reversed',
                     'is_integer','is_decimal','is_text','is_boolean','is_list','is_nothing',
                     'is_number','char_code','from_char_code'}
        if node.name in builtins:
            return self._compile_builtin_call(node)
        if node.name in self.functions:
            func_info = self.functions[node.name]
            func = func_info[0]
            func_node = func_info[1]
            args = []
            for i, arg in enumerate(node.arguments):
                v = self._compile_expr(arg)
                expected_type = func.args[i].type if i < len(func.args) else self.i8_ptr
                # Convert value to match expected parameter type
                v = self._coerce_to_type(v, expected_type)
                args.append(v)
            # Handle default params if fewer args provided
            while len(args) < len(func.args):
                pi = len(args)
                if pi < len(func_node.params) and len(func_node.params[pi]) > 2 and func_node.params[pi][2] is not None:
                    default_val = self._compile_expr(func_node.params[pi][2])
                    default_val = self._coerce_to_type(default_val, func.args[pi].type)
                    args.append(default_val)
                else:
                    args.append(ir.Constant(func.args[pi].type, None if isinstance(func.args[pi].type, ir.PointerType) else 0))
            return self.builder.call(func, args)
        return ir.Constant(self.i8_ptr, None)

    def _compile_builtin_call(self, node):
        args = [self._compile_expr(a) for a in node.arguments]
        n = node.name
        if n == 'length':
            v = args[0]
            if isinstance(v.type, ir.PointerType): return self.builder.call(self.rt_str_length, [v])
            return ir.Constant(self.i64, 0)
        if n == 'sqrt':
            v = args[0]
            if isinstance(v.type, ir.IntType): v = self.builder.sitofp(v, self.f64)
            return self.builder.call(self.rt_sqrt, [v])
        if n == 'power':
            b, e = args[0], args[1]
            if isinstance(b.type, ir.IntType): b = self.builder.sitofp(b, self.f64)
            if isinstance(e.type, ir.IntType): e = self.builder.sitofp(e, self.f64)
            return self.builder.call(self.rt_power, [b, e])
        if n == 'floor':
            v = args[0]
            if isinstance(v.type, ir.IntType): v = self.builder.sitofp(v, self.f64)
            r = self.builder.call(self.rt_floor, [v])
            return self.builder.fptosi(r, self.i64)
        if n == 'ceil':
            v = args[0]
            if isinstance(v.type, ir.IntType): v = self.builder.sitofp(v, self.f64)
            r = self.builder.call(self.rt_ceil, [v])
            return self.builder.fptosi(r, self.i64)
        if n == 'absolute':
            v = args[0]
            if isinstance(v.type, ir.DoubleType): return self.builder.call(self.rt_fabs, [v])
            neg = self.builder.neg(v)
            return self.builder.select(self.builder.icmp_signed('<', v, ir.Constant(v.type, 0)), neg, v)
        if n == 'round':
            v = args[0]
            if isinstance(v.type, ir.IntType): return v
            return self.builder.fptosi(self.builder.fadd(v, ir.Constant(self.f64, 0.5)), self.i64)
        if n == 'max':
            a, b = args
            return self.builder.select(self.builder.icmp_signed('>', a, b), a, b)
        if n == 'min':
            a, b = args
            return self.builder.select(self.builder.icmp_signed('<', a, b), a, b)
        if n == 'to_integer':
            v = args[0]
            if isinstance(v.type, ir.IntType): return v
            if isinstance(v.type, ir.PointerType): return self.builder.call(self.rt_str_to_int, [v])
            if isinstance(v.type, ir.DoubleType): return self.builder.fptosi(v, self.i64)
            return ir.Constant(self.i64, 0)
        if n == 'to_text':
            v = args[0]
            if isinstance(v.type, ir.IntType) and v.type.width == 64: return self.builder.call(self.rt_int_to_str, [v])
            if isinstance(v.type, ir.DoubleType): return self.builder.call(self.rt_float_to_str, [v])
            if isinstance(v.type, ir.PointerType): return v
            return self._get_string_ptr(self._fmt_nothing)
        if n == 'to_decimal':
            v = args[0]
            if isinstance(v.type, ir.DoubleType): return v
            if isinstance(v.type, ir.IntType): return self.builder.sitofp(v, self.f64)
            if isinstance(v.type, ir.PointerType): return self.builder.call(self.rt_str_to_float, [v])
            return ir.Constant(self.f64, 0.0)
        if n == 'uppercase': return self.builder.call(self.rt_str_upper, [args[0]])
        if n == 'lowercase': return self.builder.call(self.rt_str_lower, [args[0]])
        if n in ('log', 'sin', 'cos'):
            v = args[0]
            if isinstance(v.type, ir.IntType): v = self.builder.sitofp(v, self.f64)
            fn = {'log': self.rt_log, 'sin': self.rt_sin, 'cos': self.rt_cos}[n]
            return self.builder.call(fn, [v])
        if n == 'char_code':
            ch = self.builder.load(self.builder.gep(args[0], [ir.Constant(self.i64, 0)]))
            return self.builder.zext(ch, self.i64)
        if n == 'from_char_code':
            buf = self.builder.call(self.malloc, [ir.Constant(self.i64, 2)])
            self.builder.store(self.builder.trunc(args[0], self.i8), self.builder.gep(buf, [ir.Constant(self.i64, 0)]))
            self.builder.store(ir.Constant(self.i8, 0), self.builder.gep(buf, [ir.Constant(self.i64, 1)]))
            return buf
        return ir.Constant(self.i64, 0)

    def _compile_return(self, node):
        # Restore GC root stack before returning from function
        if self._gc_depth_var:
            self._gc_restore_depth(self._gc_depth_var)
        if node.value:
            v = self._compile_expr(node.value)
            # Coerce return value to match function's return type
            ret_type = self.func.return_value.type
            v = self._coerce_to_type(v, ret_type)
            self.builder.ret(v)
        else:
            ret_type = self.func.return_value.type
            if isinstance(ret_type, ir.PointerType):
                self.builder.ret(ir.Constant(ret_type, None))
            elif isinstance(ret_type, ir.IntType):
                self.builder.ret(ir.Constant(ret_type, 0))
            elif isinstance(ret_type, ir.DoubleType):
                self.builder.ret(ir.Constant(ret_type, 0.0))
            else:
                self.builder.ret(ir.Constant(self.i8_ptr, None))

    def _compile_break(self, node):
        if self.break_block:
            if self._loop_gc_depth:
                self._gc_restore_depth(self._loop_gc_depth)
            self.builder.branch(self.break_block)

    def _compile_continue(self, node):
        if self.continue_block:
            if self._loop_gc_depth:
                self._gc_restore_depth(self._loop_gc_depth)
            self.builder.branch(self.continue_block)

    # ─── Match ───────────────────────────────────────────

    def _compile_match(self, node):
        mv = self._compile_expr(node.expression)
        end_bb = self.func.append_basic_block('match_end')
        for clause in node.when_clauses:
            when_bb = self.func.append_basic_block('when_body')
            next_bb = self.func.append_basic_block('when_next')
            for ve in clause.values:
                cv = self._compile_expr(ve)
                if isinstance(mv.type, ir.PointerType) and isinstance(cv.type, ir.PointerType):
                    cmp = self.builder.icmp_signed('==', self.builder.call(self.strcmp, [mv, cv]), ir.Constant(self.i32, 0))
                else:
                    cmp = self.builder.icmp_signed('==', mv, cv)
                cn = self.func.append_basic_block('when_check')
                self.builder.cbranch(cmp, when_bb, cn)
                self.builder.position_at_start(cn)
            self.builder.branch(next_bb)
            self.builder.position_at_start(when_bb)
            for s in clause.body:
                if s: self._compile_stmt(s)
            if not self.builder.block.is_terminated: self.builder.branch(end_bb)
            self.builder.position_at_start(next_bb)
        if node.default_body:
            for s in node.default_body:
                if s: self._compile_stmt(s)
        if not self.builder.block.is_terminated: self.builder.branch(end_bb)
        self.builder.position_at_start(end_bb)

    # ─── Assert / Exit / Wait / Throw / Try ──────────────

    def _compile_assert(self, node):
        r = self._to_bool(self._compile_expr(node.expression))
        fail_bb = self.func.append_basic_block('af')
        ok_bb = self.func.append_basic_block('ao')
        self.builder.cbranch(r, ok_bb, fail_bb)
        self.builder.position_at_start(fail_bb)
        msg = self._make_global_string(f"Assertion failed on line {node.line}\n", f"am_{node.line}")
        self.builder.call(self.printf, [self._get_string_ptr(msg)])
        self.builder.call(self.exit_fn, [ir.Constant(self.i32, 1)])
        self.builder.unreachable()
        self.builder.position_at_start(ok_bb)

    def _compile_exit(self, node):
        self.builder.call(self.exit_fn, [ir.Constant(self.i32, 0)])
        self.builder.unreachable()

    def _compile_wait(self, node):
        d = self._compile_expr(node.duration)
        if isinstance(d.type, ir.IntType):
            ms = self.builder.trunc(self.builder.mul(d, ir.Constant(self.i64, 1000)), self.i32)
        else:
            ms = self.builder.fptosi(self.builder.fmul(d, ir.Constant(self.f64, 1000.0)), self.i32)
        self.builder.call(self.sleep_fn, [ms])

    def _compile_throw(self, node):
        msg = self._compile_expr(node.expression)
        # Ensure msg is a string pointer
        if not isinstance(msg.type, ir.PointerType):
            msg_str = self.builder.call(self.rt_int_to_str, [msg])
        else:
            msg_str = msg
        self.builder.call(self.rt_throw, [msg_str])
        self.builder.unreachable()

    def _compile_try_catch(self, node):
        # Real exception handling using setjmp/longjmp runtime functions.
        # epl_try_begin() calls setjmp and returns 0 for normal entry,
        # non-zero when an exception is caught via longjmp.
        try_bb = self.builder.append_basic_block('try')
        catch_bb = self.builder.append_basic_block('catch')
        end_bb = self.builder.append_basic_block('try_end')

        # Call epl_try_begin() — returns 0 for normal, 1 for exception
        result = self.builder.call(self.rt_try_begin, [])
        cond = self.builder.icmp_unsigned('!=', result, ir.Constant(self.i32, 0))
        self.builder.cbranch(cond, catch_bb, try_bb)

        # Try body
        self.builder.position_at_start(try_bb)
        for s in node.try_body:
            if s: self._compile_stmt(s)
        if not self.builder.block.is_terminated:
            self.builder.call(self.rt_try_end, [])
            self.builder.branch(end_bb)

        # Catch block: retrieve exception message and bind to catch_var
        self.builder.position_at_start(catch_bb)
        if hasattr(node, 'catch_var') and node.catch_var:
            exc_msg = self.builder.call(self.rt_get_exception, [])
            if node.catch_var not in self.variables:
                a = self.builder.alloca(self.i8_ptr, name=node.catch_var)
                self.variables[node.catch_var] = a
                self.var_types[node.catch_var] = 'string'
            self.builder.store(exc_msg, self.variables[node.catch_var])
        for s in node.catch_body:
            if s: self._compile_stmt(s)
        if not self.builder.block.is_terminated:
            self.builder.branch(end_bb)

        self.builder.position_at_start(end_bb)

    # ─── Classes / Enums ─────────────────────────────────

    def _compile_class_def(self, node):
        self.class_defs[node.name] = node
        props = {}

        # Handle inheritance — copy parent class properties
        parent_name = getattr(node, 'parent', None)
        if parent_name and parent_name in self.class_props:
            props.update(self.class_props[parent_name])

        # Register class in runtime class registry
        class_name_str = self._make_global_string(node.name, f"cls_reg_{node.name}")
        if parent_name:
            parent_name_str = self._make_global_string(parent_name, f"cls_parent_{parent_name}")
        else:
            parent_name_str = None

        for item in node.body:
            if isinstance(item, ast.VarDeclaration):
                props[item.name] = item.value
            elif isinstance(item, ast.ConstDeclaration):
                props[item.name] = item.value
            elif isinstance(item, ast.FunctionDef):
                mn = f"{node.name}_{item.name}"
                # Add 'self' as first parameter for methods
                method_params = list(item.params)
                if not method_params or (method_params and method_params[0][0] != 'self'):
                    method_params.insert(0, ('self',))
                md = ast.FunctionDef(mn, method_params, item.return_type if hasattr(item, 'return_type') else None, item.body, item.line)
                self._register_function(md)
                self._compile_function_def(md)
            elif isinstance(item, ast.StaticMethodDef):
                # Static methods have no 'self' parameter — compiled with ClassName_ prefix
                mn = f"{node.name}_{item.name}"
                md = ast.FunctionDef(mn, item.params, item.return_type, item.body, item.line)
                self._register_function(md)
                self._compile_function_def(md)
            elif isinstance(item, ast.VisibilityModifier):
                # Unwrap visibility — compile the inner statement
                inner = item.statement
                if isinstance(inner, ast.VarDeclaration):
                    props[inner.name] = inner.value
                elif isinstance(inner, ast.FunctionDef):
                    mn = f"{node.name}_{inner.name}"
                    method_params = list(inner.params)
                    if not method_params or (method_params and method_params[0][0] != 'self'):
                        method_params.insert(0, ('self',))
                    md = ast.FunctionDef(mn, method_params, inner.return_type if hasattr(inner, 'return_type') else None, inner.body, inner.line)
                    self._register_function(md)
                    self._compile_function_def(md)
                elif isinstance(inner, ast.StaticMethodDef):
                    mn = f"{node.name}_{inner.name}"
                    md = ast.FunctionDef(mn, inner.params, inner.return_type, inner.body, inner.line)
                    self._register_function(md)
                    self._compile_function_def(md)
            elif isinstance(item, ast.AbstractMethodDef):
                pass  # Abstract methods have no body

        # Also inherit parent methods that weren't overridden
        if parent_name and parent_name in self.class_defs:
            parent_node = self.class_defs[parent_name]
            child_methods = {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
            for item in parent_node.body:
                if isinstance(item, ast.FunctionDef) and item.name not in child_methods:
                    # This parent method is inherited — register alias
                    parent_mn = f"{parent_name}_{item.name}"
                    child_mn = f"{node.name}_{item.name}"
                    if parent_mn in self.functions and child_mn not in self.functions:
                        self.functions[child_mn] = self.functions[parent_mn]

        self.class_props[node.name] = props

    def _compile_enum_def(self, node):
        self.enum_defs[node.name] = {name: i for i, name in enumerate(node.members)}

    # ─── Method Calls / Properties / Index ────────────────

    def _compile_method_call_stmt(self, node):
        return self._compile_method_call_expr(node)

    def _compile_method_call_expr(self, node):
        obj = self._compile_expr(node.obj)
        m = node.method_name
        args = [self._compile_expr(a) for a in node.arguments]

        # List methods — check BEFORE generic pointer check since lists are also i8*
        if isinstance(node.obj, ast.Identifier) and self.var_types.get(node.obj.name) == 'list':
            if m in ('add','push'):
                v = args[0]
                if isinstance(v.type, ir.IntType) and v.type.width == 64:
                    self.builder.call(self.rt_list_push, [obj, ir.Constant(self.i32, TAG_INT), v])
                elif isinstance(v.type, ir.PointerType):
                    self.builder.call(self.rt_list_push, [obj, ir.Constant(self.i32, TAG_STRING), self.builder.ptrtoint(v, self.i64)])
                return ir.Constant(self.i64, 0)
            if m == 'remove':
                self.builder.call(self.rt_list_remove, [obj, args[0] if isinstance(args[0].type, ir.IntType) and args[0].type.width == 64 else self.builder.sext(args[0], self.i64)])
                return ir.Constant(self.i64, 0)
            if m == 'length':
                return self.builder.sext(self.builder.call(self.rt_list_length, [obj]), self.i64)
            if m == 'contains':
                v = args[0]
                v64 = v if isinstance(v.type, ir.IntType) and v.type.width == 64 else self.builder.sext(v, self.i64)
                return self.builder.trunc(self.builder.call(self.rt_list_contains_int, [obj, v64]), self.i1)

        # String methods
        if (isinstance(node.obj, ast.Identifier) and self.var_types.get(node.obj.name) == 'string') or isinstance(obj.type, ir.PointerType):
            if m in ('uppercase','upper'): return self.builder.call(self.rt_str_upper, [obj])
            if m in ('lowercase','lower'): return self.builder.call(self.rt_str_lower, [obj])
            if m == 'trim': return self.builder.call(self.rt_str_trim, [obj])
            if m == 'contains': return self.builder.trunc(self.builder.call(self.rt_str_contains, [obj, args[0]]), self.i1)
            if m == 'replace': return self.builder.call(self.rt_str_replace, [obj, args[0], args[1]])
            if m == 'starts_with': return self.builder.trunc(self.builder.call(self.rt_str_starts_with, [obj, args[0]]), self.i1)
            if m == 'ends_with': return self.builder.trunc(self.builder.call(self.rt_str_ends_with, [obj, args[0]]), self.i1)
            if m == 'split': return self.builder.call(self.rt_str_split, [obj, args[0]])
            if m == 'substring':
                a0 = args[0] if isinstance(args[0].type, ir.IntType) and args[0].type.width == 64 else self.builder.sext(args[0], self.i64)
                a1 = args[1] if isinstance(args[1].type, ir.IntType) and args[1].type.width == 64 else self.builder.sext(args[1], self.i64)
                return self.builder.call(self.rt_str_substring, [obj, a0, a1])
            if m == 'reverse': return self.builder.call(self.rt_str_reverse, [obj])
            if m == 'length': return self.builder.call(self.rt_str_length, [obj])
            if m == 'repeat':
                a0 = args[0] if isinstance(args[0].type, ir.IntType) and args[0].type.width == 64 else self.builder.sext(args[0], self.i64)
                return self.builder.call(self.rt_str_repeat, [obj, a0])
            if m == 'index_of' or m == 'find':
                return self.builder.call(self.rt_str_index_of, [obj, args[0]])

        # Dict/Map methods
        if isinstance(node.obj, ast.Identifier) and self.var_types.get(node.obj.name) == 'map':
            if m == 'keys': return self.builder.call(self.rt_map_keys, [obj])
            if m == 'values': return self.builder.call(self.rt_map_values, [obj])
            if m == 'has_key' or m == 'has':
                kp = args[0] if isinstance(args[0].type, ir.PointerType) else self._get_string_ptr(self._make_global_string("", "empty"))
                return self.builder.trunc(self.builder.call(self.rt_map_has_key, [obj, kp]), self.i1)
            if m == 'remove':
                kp = args[0] if isinstance(args[0].type, ir.PointerType) else self._get_string_ptr(self._make_global_string("", "empty"))
                self.builder.call(self.rt_map_remove, [obj, kp])
                return ir.Constant(self.i64, 0)
            if m == 'length' or m == 'size':
                return self.builder.sext(self.builder.call(self.rt_map_size, [obj]), self.i64)

        # Class method — pass object as 'self' first argument
        for cn in self.class_defs:
            mn = f"{cn}_{m}"
            if mn in self.functions:
                func, _ = self.functions[mn][:2]
                ca = [obj]  # Pass object as 'self'
                for a in args:
                    if isinstance(a.type, ir.IntType) and a.type.width != 64: a = self.builder.sext(a, self.i64)
                    ca.append(a)
                # Coerce arguments to match function parameter types
                final_args = []
                for i, a in enumerate(ca):
                    if i < len(func.args):
                        a = self._coerce_to_type(a, func.args[i].type)
                    final_args.append(a)
                return self.builder.call(func, final_args)
        return ir.Constant(self.i64, 0)

    def _compile_property_set(self, node):
        obj = self._compile_expr(node.obj)
        v = self._compile_expr(node.value)
        pn = self._make_global_string(node.property_name, f"prop_{node.property_name}")
        pp = self._get_string_ptr(pn)
        if isinstance(v.type, ir.IntType):
            self.builder.call(self.rt_obj_set_int, [obj, pp, v if v.type.width == 64 else self.builder.sext(v, self.i64)])
        elif isinstance(v.type, ir.PointerType):
            self.builder.call(self.rt_obj_set_str, [obj, pp, v])

    def _compile_index_set(self, node):
        obj = self._compile_expr(node.obj)
        idx = self._compile_expr(node.index)
        val = self._compile_expr(node.value)
        idx64 = idx if isinstance(idx.type, ir.IntType) and idx.type.width == 64 else self.builder.sext(idx, self.i64)
        if isinstance(val.type, ir.IntType):
            v64 = val if val.type.width == 64 else self.builder.sext(val, self.i64)
            self.builder.call(self.rt_list_set_int, [obj, idx64, v64])
        elif isinstance(val.type, ir.DoubleType):
            # Store float as bitcast i64 in list
            v64 = self.builder.bitcast(val, self.i64)
            self.builder.call(self.rt_list_set_int, [obj, idx64, v64])
        elif isinstance(val.type, ir.PointerType):
            # Store string pointer as i64 in list
            v64 = self.builder.ptrtoint(val, self.i64)
            self.builder.call(self.rt_list_set_int, [obj, idx64, v64])

    # ─── File I/O ────────────────────────────────────────

    def _compile_file_write(self, node):
        c = self._compile_expr(node.content)
        fp = self._compile_expr(node.filepath)
        mode = self._make_global_string("w", "fmode_w")
        f = self.builder.call(self.fopen, [fp, self._get_string_ptr(mode)])
        self.builder.call(self.fprintf, [f, self._get_string_ptr(self._fmt_str), c])
        self.builder.call(self.fclose, [f])

    def _compile_file_append(self, node):
        c = self._compile_expr(node.content)
        fp = self._compile_expr(node.filepath)
        mode = self._make_global_string("a", "fmode_a")
        f = self.builder.call(self.fopen, [fp, self._get_string_ptr(mode)])
        self.builder.call(self.fprintf, [f, self._get_string_ptr(self._fmt_str_nl), c])
        self.builder.call(self.fclose, [f])

    def _compile_import(self, node):
        import os
        fp = os.path.abspath(node.filepath)
        if not os.path.exists(fp): return
        try:
            with open(fp, 'r', encoding='utf-8') as f: src = f.read()
            from epl.lexer import Lexer; from epl.parser import Parser
            prog = Parser(Lexer(src).tokenize()).parse()
            for s in prog.statements:
                if isinstance(s, ast.FunctionDef):
                    self._register_function(s)
                    self._compile_function_def(s)
        except Exception as e:
            import sys
            print(f"Warning: Failed to compile import '{node.filepath}': {e}", file=sys.stderr)

    # ─── Expression Dispatch ─────────────────────────────

    def _compile_expr(self, node):
        if isinstance(node, ast.Literal): return self._compile_literal(node)
        if isinstance(node, ast.Identifier): return self._compile_identifier(node)
        if isinstance(node, ast.BinaryOp): return self._compile_binary(node)
        if isinstance(node, ast.UnaryOp): return self._compile_unary(node)
        if isinstance(node, ast.FunctionCall): return self._compile_function_call(node)
        if isinstance(node, ast.PropertyAccess): return self._compile_property_access(node)
        if isinstance(node, ast.MethodCall): return self._compile_method_call_expr(node)
        if isinstance(node, ast.IndexAccess): return self._compile_index_access(node)
        if isinstance(node, ast.SliceAccess): return self._compile_slice_access(node)
        if isinstance(node, ast.ListLiteral): return self._compile_list_literal(node)
        if isinstance(node, ast.DictLiteral): return self._compile_dict_literal(node)
        if isinstance(node, ast.NewInstance): return self._compile_new_instance(node)
        if isinstance(node, ast.FileRead): return self._compile_file_read(node)
        if isinstance(node, ast.LambdaExpression): return self._compile_lambda(node)
        if isinstance(node, ast.TernaryExpression): return self._compile_ternary(node)
        # v4.0: Expression nodes
        if isinstance(node, ast.AwaitExpression): return self._compile_expr(node.expression)
        if isinstance(node, ast.ModuleAccess): return self._compile_module_access_expr(node)
        if isinstance(node, ast.SuperCall): return self._compile_super_call_expr(node)
        if isinstance(node, ast.SpreadExpression): return self._compile_expr(node.expression)
        if isinstance(node, ast.ChainedComparison): return self._compile_chained_comparison(node)
        return ir.Constant(self.i64, 0)

    def _compile_identifier(self, node):
        if node.name in self.variables:
            return self.builder.load(self.variables[node.name], name=node.name)
        return ir.Constant(self.i64, 0)

    def _compile_literal(self, node):
        if isinstance(node.value, bool): return ir.Constant(self.i1, 1 if node.value else 0)
        if isinstance(node.value, int): return ir.Constant(self.i64, node.value)
        if isinstance(node.value, float): return ir.Constant(self.f64, node.value)
        if isinstance(node.value, str):
            if '$' in node.value and ('{' in node.value or any(c.isalpha() for c in node.value.split('$')[1:])):
                return self._compile_template_string(node.value)
            gs = self._make_global_string(node.value, f"str_{len(self.string_constants)}")
            return self._get_string_ptr(gs)
        return ir.Constant(self.i64, 0)

    _TEMPLATE_RE = _re.compile(r'\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)')

    def _compile_template_string(self, text):
        """Compile a template string with ${expr} and $var interpolation.
        Splits into literal segments and expression segments, compiles each,
        and concatenates the results."""
        parts = []
        last_end = 0
        for m in self._TEMPLATE_RE.finditer(text):
            # Add literal part before this match
            if m.start() > last_end:
                parts.append(('literal', text[last_end:m.start()]))
            if m.group(1) is not None:
                parts.append(('expr', m.group(1)))
            elif m.group(2) is not None:
                parts.append(('var', m.group(2)))
            last_end = m.end()
        # Add trailing literal
        if last_end < len(text):
            parts.append(('literal', text[last_end:]))

        if not parts:
            gs = self._make_global_string("", f"str_{len(self.string_constants)}")
            return self._get_string_ptr(gs)

        def compile_part(kind, value):
            if kind == 'literal':
                gs = self._make_global_string(value, f"str_{len(self.string_constants)}")
                return self._get_string_ptr(gs)
            elif kind == 'var':
                if value in self.variables:
                    v = self.builder.load(self.variables[value], name=value)
                    return self._value_to_string(v)
                # Unknown variable — emit the raw text
                gs = self._make_global_string(f"${value}", f"str_{len(self.string_constants)}")
                return self._get_string_ptr(gs)
            elif kind == 'expr':
                try:
                    from epl.lexer import Lexer as _Lexer
                    from epl.parser import Parser as _Parser
                    lexer = _Lexer(value)
                    tokens = lexer.tokenize()
                    parser = _Parser(tokens)
                    expr_node = parser._parse_expression()
                    v = self._compile_expr(expr_node)
                    return self._value_to_string(v)
                except Exception:
                    gs = self._make_global_string(f"${{{value}}}", f"str_{len(self.string_constants)}")
                    return self._get_string_ptr(gs)

        result = compile_part(*parts[0])
        for p in parts[1:]:
            right = compile_part(*p)
            result = self._compile_str_concat(result, right)
        return result

    def _value_to_string(self, v):
        """Convert an LLVM value to a string pointer for template interpolation."""
        if isinstance(v.type, ir.PointerType):
            return v
        if isinstance(v.type, ir.IntType):
            if v.type.width == 1:
                # Boolean
                true_gs = self._make_global_string("true", f"str_{len(self.string_constants)}")
                false_gs = self._make_global_string("false", f"str_{len(self.string_constants)}")
                return self.builder.select(v, self._get_string_ptr(true_gs), self._get_string_ptr(false_gs))
            if v.type.width == 64:
                return self.builder.call(self.rt_int_to_str, [v])
            extended = self.builder.sext(v, self.i64)
            return self.builder.call(self.rt_int_to_str, [extended])
        if isinstance(v.type, ir.DoubleType):
            return self.builder.call(self.rt_float_to_str, [v])
        gs = self._make_global_string("<unknown>", f"str_{len(self.string_constants)}")
        return self._get_string_ptr(gs)

    def _compile_binary(self, node):
        left = self._compile_expr(node.left)
        right = self._compile_expr(node.right)

        if isinstance(left.type, ir.PointerType) and isinstance(right.type, ir.PointerType):
            if node.operator == '+': return self._compile_str_concat(left, right)
            if node.operator == '==':
                return self.builder.icmp_signed('==', self.builder.call(self.strcmp, [left, right]), ir.Constant(self.i32, 0))
            if node.operator == '!=':
                return self.builder.icmp_signed('!=', self.builder.call(self.strcmp, [left, right]), ir.Constant(self.i32, 0))

        if isinstance(left.type, ir.PointerType) and isinstance(right.type, ir.IntType) and node.operator == '+':
            rs = self.builder.call(self.rt_int_to_str, [right if right.type.width == 64 else self.builder.sext(right, self.i64)])
            return self._compile_str_concat(left, rs)
        if isinstance(left.type, ir.IntType) and isinstance(right.type, ir.PointerType) and node.operator == '+':
            ls = self.builder.call(self.rt_int_to_str, [left if left.type.width == 64 else self.builder.sext(left, self.i64)])
            return self._compile_str_concat(ls, right)

        # Coerce pointer to i64 for arithmetic/comparison with integers
        if isinstance(left.type, ir.PointerType) and isinstance(right.type, ir.IntType) and node.operator not in ('+',):
            left = self.builder.ptrtoint(left, self.i64)
        if isinstance(right.type, ir.PointerType) and isinstance(left.type, ir.IntType) and node.operator not in ('+',):
            right = self.builder.ptrtoint(right, self.i64)

        if node.operator == '**':
            if isinstance(left.type, ir.IntType): left = self.builder.sitofp(left, self.f64)
            if isinstance(right.type, ir.IntType): right = self.builder.sitofp(right, self.f64)
            return self.builder.call(self.rt_power, [left, right])

        if node.operator == '//':
            if isinstance(left.type, ir.DoubleType) or isinstance(right.type, ir.DoubleType):
                if isinstance(left.type, ir.IntType): left = self.builder.sitofp(left, self.f64)
                if isinstance(right.type, ir.IntType): right = self.builder.sitofp(right, self.f64)
                return self.builder.call(self.rt_floor, [self.builder.fdiv(left, right)])
            self._check_div_by_zero(right)
            return self.builder.sdiv(left, right)

        if isinstance(left.type, ir.DoubleType) or isinstance(right.type, ir.DoubleType):
            if isinstance(left.type, ir.IntType): left = self.builder.sitofp(left, self.f64)
            if isinstance(right.type, ir.IntType): right = self.builder.sitofp(right, self.f64)
            return self._compile_float_binary(node.operator, left, right)

        if isinstance(left.type, ir.IntType) and isinstance(right.type, ir.IntType):
            if left.type.width < right.type.width: left = self.builder.sext(left, right.type)
            elif right.type.width < left.type.width: right = self.builder.sext(right, left.type)
        return self._compile_int_binary(node.operator, left, right)

    def _compile_int_binary(self, op, l, r):
        m = {'+':'add','-':'sub','*':'mul','/':'sdiv','%':'srem'}
        if op in m:
            if op in ('/', '%'):
                self._check_div_by_zero(r)
            return getattr(self.builder, m[op])(l, r)
        cm = {'>':'>','<':'<','>=':'>=','<=':'<=','==':'==','!=':'!='}
        if op in cm: return self.builder.icmp_signed(cm[op], l, r)
        if op == 'and': return self.builder.and_(l, r)
        if op == 'or': return self.builder.or_(l, r)
        return ir.Constant(self.i64, 0)

    def _compile_float_binary(self, op, l, r):
        m = {'+':'fadd','-':'fsub','*':'fmul','/':'fdiv','%':'frem'}
        if op in m: return getattr(self.builder, m[op])(l, r)
        cm = {'>':'>','<':'<','>=':'>=','<=':'<=','==':'==','!=':'!='}
        if op in cm: return self.builder.fcmp_ordered(cm[op], l, r)
        return ir.Constant(self.f64, 0.0)

    def _compile_unary(self, node):
        o = self._compile_expr(node.operand)
        if node.operator == '-':
            return self.builder.fneg(o) if isinstance(o.type, ir.DoubleType) else self.builder.neg(o)
        if node.operator == 'not':
            if isinstance(o.type, ir.IntType) and o.type.width == 1: return self.builder.not_(o)
            if isinstance(o.type, ir.IntType): return self.builder.icmp_signed('==', o, ir.Constant(o.type, 0))
            if isinstance(o.type, ir.DoubleType): return self.builder.fcmp_ordered('==', o, ir.Constant(self.f64, 0.0))
            if isinstance(o.type, ir.PointerType): return self.builder.icmp_signed('==', self.builder.ptrtoint(o, self.i64), ir.Constant(self.i64, 0))
        return o

    def _compile_str_concat(self, left, right):
        return self.builder.call(self.rt_gc_str_concat, [left, right])

    # ─── Lambda / Ternary / Slice ─────────────────────────

    def _compile_lambda(self, node):
        self.lambda_counter += 1
        name = f"__lambda_{self.lambda_counter}"

        # Detect captured variables (referenced in lambda body but defined in outer scope)
        captured_vars = []
        body_vars = self._collect_identifiers(node.body)
        for var_name in body_vars:
            if var_name in self.variables and var_name not in node.params:
                captured_vars.append(var_name)

        if captured_vars:
            # Lambda with closure — extra first param is closure environment pointer
            param_types = [self.i8_ptr] + [self.i64] * len(node.params)
            fty = ir.FunctionType(self.i64, param_types)
            func = ir.Function(self.module, fty, name=name)
            ob, of, ov, ot = self.builder, self.func, self.variables.copy(), self.var_types.copy()
            block = func.append_basic_block(name="entry")
            self.builder = ir.IRBuilder(block)
            self.func = func
            self.variables = {}

            # Restore captured variables from closure environment
            closure_ptr = func.args[0]
            for ci, cvar in enumerate(captured_vars):
                val = self.builder.call(self.rt_closure_get, [closure_ptr, ir.Constant(self.i32, ci)])
                orig_type = ov.get(cvar, 'int')
                if orig_type == 'float':
                    # bitcast i64 back to f64 to preserve float precision
                    fval = self.builder.bitcast(val, self.f64)
                    a = self.builder.alloca(self.f64, name=cvar)
                    self.builder.store(fval, a)
                else:
                    a = self.builder.alloca(self.i64, name=cvar)
                    self.builder.store(val, a)
                self.variables[cvar] = a
                self.var_types[cvar] = orig_type

            # Regular parameters (offset by 1 due to closure pointer)
            for i, p in enumerate(node.params):
                a = self.builder.alloca(self.i64, name=p)
                self.builder.store(func.args[i + 1], a)
                self.variables[p] = a
                self.var_types[p] = 'int'

            r = self._compile_expr(node.body)
            if isinstance(r.type, ir.IntType) and r.type.width != 64: r = self.builder.sext(r, self.i64)
            elif isinstance(r.type, ir.DoubleType): r = self.builder.bitcast(r, self.i64)
            elif isinstance(r.type, ir.PointerType): r = self.builder.ptrtoint(r, self.i64)
            self.builder.ret(r)
            self.builder, self.func, self.variables, self.var_types = ob, of, ov, ot
            self.functions[name] = (func, None)

            # Create closure environment object and capture current values
            env = self.builder.call(self.rt_closure_new, [ir.Constant(self.i32, len(captured_vars))])
            for ci, cvar in enumerate(captured_vars):
                if cvar in self.variables:
                    val = self.builder.load(self.variables[cvar])
                    val64 = val
                    if isinstance(val.type, ir.IntType) and val.type.width != 64:
                        val64 = self.builder.sext(val, self.i64)
                    elif isinstance(val.type, ir.PointerType):
                        val64 = self.builder.ptrtoint(val, self.i64)
                    elif isinstance(val.type, ir.DoubleType):
                        val64 = self.builder.bitcast(val, self.i64)
                    tag = ir.Constant(self.i32, TAG_INT)
                    if self.var_types.get(cvar) == 'string':
                        tag = ir.Constant(self.i32, TAG_STRING)
                    elif self.var_types.get(cvar) == 'float':
                        tag = ir.Constant(self.i32, TAG_FLOAT)
                    self.builder.call(self.rt_closure_set, [env, ir.Constant(self.i32, ci), tag, val64])

            # Store closure: pack function pointer and env pointer together
            # We return function pointer; closure env is stored as global for this lambda
            closure_var_name = f"__closure_env_{self.lambda_counter}"
            g_env = ir.GlobalVariable(self.module, self.i8_ptr, name=closure_var_name)
            g_env.linkage = 'internal'
            g_env.initializer = ir.Constant(self.i8_ptr, None)
            self.builder.store(env, g_env)
            self._closure_envs = getattr(self, '_closure_envs', {})
            self._closure_envs[name] = g_env

            return self.builder.ptrtoint(func, self.i64)
        else:
            # Simple lambda without closure (original behavior)
            fty = ir.FunctionType(self.i64, [self.i64] * len(node.params))
            func = ir.Function(self.module, fty, name=name)
            ob, of, ov, ot = self.builder, self.func, self.variables.copy(), self.var_types.copy()
            block = func.append_basic_block(name="entry")
            self.builder = ir.IRBuilder(block)
            self.func = func
            self.variables = {}
            for i, p in enumerate(node.params):
                a = self.builder.alloca(self.i64, name=p)
                self.builder.store(func.args[i], a)
                self.variables[p] = a
                self.var_types[p] = 'int'
            r = self._compile_expr(node.body)
            if isinstance(r.type, ir.IntType) and r.type.width != 64: r = self.builder.sext(r, self.i64)
            elif isinstance(r.type, ir.DoubleType): r = self.builder.bitcast(r, self.i64)
            elif isinstance(r.type, ir.PointerType): r = self.builder.ptrtoint(r, self.i64)
            self.builder.ret(r)
            self.builder, self.func, self.variables, self.var_types = ob, of, ov, ot
            self.functions[name] = (func, None)
            return self.builder.ptrtoint(func, self.i64)

    def _collect_identifiers(self, node):
        """Collect all identifier names referenced in an expression/statement subtree."""
        names = set()
        if isinstance(node, ast.Identifier):
            names.add(node.name)
        elif isinstance(node, ast.BinaryOp):
            names |= self._collect_identifiers(node.left)
            names |= self._collect_identifiers(node.right)
        elif isinstance(node, ast.UnaryOp):
            names |= self._collect_identifiers(node.operand)
        elif isinstance(node, ast.FunctionCall):
            for a in node.arguments:
                names |= self._collect_identifiers(a)
        elif isinstance(node, ast.MethodCall):
            names |= self._collect_identifiers(node.obj)
            for a in node.arguments:
                names |= self._collect_identifiers(a)
        elif isinstance(node, ast.PropertyAccess):
            names |= self._collect_identifiers(node.obj)
        elif isinstance(node, ast.IndexAccess):
            names |= self._collect_identifiers(node.obj)
            names |= self._collect_identifiers(node.index)
        elif isinstance(node, ast.TernaryExpression):
            names |= self._collect_identifiers(node.condition)
            names |= self._collect_identifiers(node.true_expr)
            names |= self._collect_identifiers(node.false_expr)
        elif isinstance(node, ast.ListLiteral):
            for e in node.elements:
                names |= self._collect_identifiers(e)
        elif isinstance(node, ast.DictLiteral):
            for _, v in node.pairs:
                names |= self._collect_identifiers(v)
        return names

    def _compile_ternary(self, node):
        cond = self._to_bool(self._compile_expr(node.condition))
        then_bb = self.func.append_basic_block('t_then')
        else_bb = self.func.append_basic_block('t_else')
        merge_bb = self.func.append_basic_block('t_merge')
        self.builder.cbranch(cond, then_bb, else_bb)
        self.builder.position_at_start(then_bb)
        tv = self._compile_expr(node.true_expr)
        tbb = self.builder.block
        self.builder.branch(merge_bb)
        self.builder.position_at_start(else_bb)
        fv = self._compile_expr(node.false_expr)
        fbb = self.builder.block
        self.builder.branch(merge_bb)
        self.builder.position_at_start(merge_bb)
        if tv.type == fv.type:
            phi = self.builder.phi(tv.type, 'tern')
            phi.add_incoming(tv, tbb)
            phi.add_incoming(fv, fbb)
        else:
            # Coerce both to the same type
            if isinstance(tv.type, ir.DoubleType) or isinstance(fv.type, ir.DoubleType):
                # Promote to float
                phi = self.builder.phi(self.f64, 'tern')
                tv_c = tv if isinstance(tv.type, ir.DoubleType) else self.builder.sitofp(tv, self.f64) if isinstance(tv.type, ir.IntType) else self.builder.bitcast(self.builder.ptrtoint(tv, self.i64), self.f64)
                fv_c = fv if isinstance(fv.type, ir.DoubleType) else self.builder.sitofp(fv, self.f64) if isinstance(fv.type, ir.IntType) else self.builder.bitcast(self.builder.ptrtoint(fv, self.i64), self.f64)
                phi.add_incoming(tv_c, tbb)
                phi.add_incoming(fv_c, fbb)
            elif isinstance(tv.type, ir.PointerType) or isinstance(fv.type, ir.PointerType):
                # Promote to pointer
                phi = self.builder.phi(self.i8_ptr, 'tern')
                tv_c = tv if isinstance(tv.type, ir.PointerType) else self.builder.inttoptr(tv, self.i8_ptr) if isinstance(tv.type, ir.IntType) else tv
                fv_c = fv if isinstance(fv.type, ir.PointerType) else self.builder.inttoptr(fv, self.i8_ptr) if isinstance(fv.type, ir.IntType) else fv
                phi.add_incoming(tv_c, tbb)
                phi.add_incoming(fv_c, fbb)
            else:
                phi = self.builder.phi(self.i64, 'tern')
                tv_c = self._coerce_to_type(tv, self.i64)
                fv_c = self._coerce_to_type(fv, self.i64)
                phi.add_incoming(tv_c, tbb)
                phi.add_incoming(fv_c, fbb)
        return phi

    def _compile_slice_access(self, node):
        obj = self._compile_expr(node.obj)
        start = self._compile_expr(node.start) if node.start else ir.Constant(self.i64, 0)
        step = self._compile_expr(node.step) if node.step else ir.Constant(self.i64, 1)
        is_list = isinstance(node.obj, ast.Identifier) and self.var_types.get(node.obj.name) == 'list'
        if is_list:
            end = self._compile_expr(node.end) if node.end else self.builder.sext(self.builder.call(self.rt_list_length, [obj]), self.i64)
            return self.builder.call(self.rt_list_slice, [obj, start, end, step])
        else:
            end = self._compile_expr(node.end) if node.end else self.builder.call(self.rt_str_length, [obj])
            return self.builder.call(self.rt_str_substring, [obj, start, end])

    # ─── Literals & Collections ───────────────────────────

    def _compile_list_literal(self, node):
        lp = self.builder.call(self.rt_gc_new_list, [])
        self._gc_push_root(lp)
        for e in node.elements:
            v = self._compile_expr(e)
            if isinstance(v.type, ir.IntType) and v.type.width == 64:
                self.builder.call(self.rt_list_push, [lp, ir.Constant(self.i32, TAG_INT), v])
            elif isinstance(v.type, ir.IntType) and v.type.width == 1:
                self.builder.call(self.rt_list_push, [lp, ir.Constant(self.i32, TAG_BOOL), self.builder.zext(v, self.i64)])
            elif isinstance(v.type, ir.PointerType):
                self.builder.call(self.rt_list_push, [lp, ir.Constant(self.i32, TAG_STRING), self.builder.ptrtoint(v, self.i64)])
            elif isinstance(v.type, ir.DoubleType):
                self.builder.call(self.rt_list_push, [lp, ir.Constant(self.i32, TAG_FLOAT), self.builder.bitcast(v, self.i64)])
            else:
                self.builder.call(self.rt_list_push, [lp, ir.Constant(self.i32, TAG_INT), self.builder.sext(v, self.i64) if isinstance(v.type, ir.IntType) else v])
        return lp

    def _compile_index_access(self, node):
        obj = self._compile_expr(node.obj)
        idx = self._compile_expr(node.index)
        idx64 = idx if isinstance(idx.type, ir.IntType) and idx.type.width == 64 else self.builder.sext(idx, self.i64)
        if isinstance(node.obj, ast.Identifier) and self.var_types.get(node.obj.name) == 'list':
            return self.builder.call(self.rt_list_get_int, [obj, idx64])
        if isinstance(obj.type, ir.PointerType):
            return self.builder.call(self.rt_str_index, [obj, idx64])
        return self.builder.call(self.rt_list_get_int, [obj, idx64])

    def _compile_dict_literal(self, node):
        mp = self.builder.call(self.rt_gc_new_map, [])
        self._gc_push_root(mp)
        for ks, vn in node.pairs:
            v = self._compile_expr(vn)
            kp = self._get_string_ptr(self._make_global_string(ks, f"mk_{ks}_{id(node)}"))
            if isinstance(v.type, ir.IntType):
                self.builder.call(self.rt_map_set_int, [mp, kp, v if v.type.width == 64 else self.builder.sext(v, self.i64)])
            elif isinstance(v.type, ir.PointerType):
                self.builder.call(self.rt_map_set_str, [mp, kp, v])
        return mp

    def _compile_new_instance(self, node):
        cn = node.class_name
        np = self._get_string_ptr(self._make_global_string(cn, f"cls_{cn}"))
        obj = self.builder.call(self.rt_gc_new_object, [np])
        self._gc_push_root(obj)

        # Inherit parent class properties first
        if cn in self.class_defs:
            class_node = self.class_defs[cn]
            parent = getattr(class_node, 'parent', None)
            if parent and parent in self.class_props:
                for pn, vn in self.class_props[parent].items():
                    v = self._compile_expr(vn)
                    pp = self._get_string_ptr(self._make_global_string(pn, f"prop_{parent}_{pn}"))
                    if isinstance(v.type, ir.IntType):
                        self.builder.call(self.rt_obj_set_int, [obj, pp, v if v.type.width == 64 else self.builder.sext(v, self.i64)])
                    elif isinstance(v.type, ir.PointerType):
                        self.builder.call(self.rt_obj_set_str, [obj, pp, v])

        # Set own properties
        if cn in self.class_props:
            for pn, vn in self.class_props[cn].items():
                v = self._compile_expr(vn)
                pp = self._get_string_ptr(self._make_global_string(pn, f"prop_{cn}_{pn}"))
                if isinstance(v.type, ir.IntType):
                    self.builder.call(self.rt_obj_set_int, [obj, pp, v if v.type.width == 64 else self.builder.sext(v, self.i64)])
                elif isinstance(v.type, ir.PointerType):
                    self.builder.call(self.rt_obj_set_str, [obj, pp, v])

        # Call constructor if defined
        constructor_name = f"{cn}_constructor"
        init_name = f"{cn}_init"
        ctor_fn_name = constructor_name if constructor_name in self.functions else (init_name if init_name in self.functions else None)
        if ctor_fn_name:
            func_info = self.functions[ctor_fn_name]
            func = func_info[0]
            # Constructor args: self + user arguments
            ctor_args = [obj]
            if hasattr(node, 'arguments'):
                for arg in node.arguments:
                    v = self._compile_expr(arg)
                    ctor_args.append(v)
            # Coerce arguments
            final_args = []
            for i, a in enumerate(ctor_args):
                if i < len(func.args):
                    a = self._coerce_to_type(a, func.args[i].type)
                final_args.append(a)
            # Pad with defaults if needed
            while len(final_args) < len(func.args):
                final_args.append(ir.Constant(func.args[len(final_args)].type, 0))
            self.builder.call(func, final_args)

        return obj

    def _compile_property_access(self, node):
        if isinstance(node.obj, ast.Identifier) and node.obj.name in self.enum_defs:
            m = self.enum_defs[node.obj.name]
            if node.property_name in m: return ir.Constant(self.i64, m[node.property_name])
        obj = self._compile_expr(node.obj)
        p = node.property_name
        if isinstance(node.obj, ast.Identifier):
            vt = self.var_types.get(node.obj.name)
            if vt == 'string':
                if p == 'length': return self.builder.call(self.rt_str_length, [obj])
                if p == 'uppercase': return self.builder.call(self.rt_str_upper, [obj])
                if p == 'lowercase': return self.builder.call(self.rt_str_lower, [obj])
                if p == 'trim': return self.builder.call(self.rt_str_trim, [obj])
            if vt == 'list':
                if p == 'length': return self.builder.sext(self.builder.call(self.rt_list_length, [obj]), self.i64)
        pp = self._get_string_ptr(self._make_global_string(p, f"prop_{p}"))
        if isinstance(obj.type, ir.PointerType):
            return self.builder.call(self.rt_obj_get_int, [obj, pp])
        return ir.Constant(self.i64, 0)

    def _compile_file_read(self, node):
        fp = self._compile_expr(node.filepath)
        return self.builder.call(self.rt_file_read, [fp])

    # ─── v4.0: Production-Level Node Compilation ─────────

    def _compile_try_catch_finally(self, node):
        """Compile Try / Catch [ErrorType] error / Finally / End with setjmp/longjmp."""
        try_bb = self.builder.append_basic_block('try4')
        catch_bb = self.builder.append_basic_block('catch4')
        finally_bb = self.builder.append_basic_block('finally4')
        end_bb = self.builder.append_basic_block('try4_end')

        result = self.builder.call(self.rt_try_begin, [])
        cond = self.builder.icmp_unsigned('!=', result, ir.Constant(self.i32, 0))
        self.builder.cbranch(cond, catch_bb, try_bb)

        # Try body
        self.builder.position_at_start(try_bb)
        for s in node.try_body:
            if s and not self.builder.block.is_terminated:
                self._compile_stmt(s)
        if not self.builder.block.is_terminated:
            self.builder.call(self.rt_try_end, [])
            self.builder.branch(finally_bb)

        # Catch block(s) — dispatch to correct clause based on error type
        self.builder.position_at_start(catch_bb)
        if node.catch_clauses:
            exc_msg = self.builder.call(self.rt_get_exception, [])
            if len(node.catch_clauses) == 1:
                # Single catch clause — no type dispatch needed
                error_type, error_var, catch_body = node.catch_clauses[0]
                if error_var:
                    if error_var not in self.variables:
                        a = self.builder.alloca(self.i8_ptr, name=error_var)
                        self.variables[error_var] = a
                        self.var_types[error_var] = 'string'
                    self.builder.store(exc_msg, self.variables[error_var])
                for s in catch_body:
                    if s and not self.builder.block.is_terminated:
                        self._compile_stmt(s)
            else:
                # Multiple catch clauses — chain type checks using starts_with
                clause_bbs = []
                check_bbs = []
                for ci in range(len(node.catch_clauses)):
                    check_bbs.append(self.builder.append_basic_block(f'catch_check_{ci}'))
                    clause_bbs.append(self.builder.append_basic_block(f'catch_body_{ci}'))
                fallthrough_bb = self.builder.append_basic_block('catch_fallthrough')
                # Jump from catch entry to first check
                self.builder.branch(check_bbs[0])
                for ci, clause in enumerate(node.catch_clauses):
                    error_type, error_var, catch_body = clause
                    # Emit type check
                    self.builder.position_at_start(check_bbs[ci])
                    if error_type:
                        type_gs = self._make_global_string(error_type, f".catch_type_{ci}")
                        type_str = self._get_string_ptr(type_gs)
                        match = self.builder.call(self.rt_str_starts_with, [exc_msg, type_str])
                        match_bool = self.builder.trunc(match, self.i1)
                        next_bb = check_bbs[ci + 1] if ci + 1 < len(node.catch_clauses) else fallthrough_bb
                        self.builder.cbranch(match_bool, clause_bbs[ci], next_bb)
                    else:
                        # No error_type means catch-all
                        self.builder.branch(clause_bbs[ci])
                    # Emit clause body
                    self.builder.position_at_start(clause_bbs[ci])
                    if error_var:
                        if error_var not in self.variables:
                            a = self.builder.alloca(self.i8_ptr, name=error_var)
                            self.variables[error_var] = a
                            self.var_types[error_var] = 'string'
                        self.builder.store(exc_msg, self.variables[error_var])
                    for s in catch_body:
                        if s and not self.builder.block.is_terminated:
                            self._compile_stmt(s)
                    if not self.builder.block.is_terminated:
                        self.builder.branch(finally_bb)
                # Fallthrough — no clause matched, go to finally
                self.builder.position_at_start(fallthrough_bb)
        if not self.builder.block.is_terminated:
            self.builder.branch(finally_bb)

        # Finally block — always executes
        self.builder.position_at_start(finally_bb)
        for s in node.finally_body:
            if s and not self.builder.block.is_terminated:
                self._compile_stmt(s)
        if not self.builder.block.is_terminated:
            self.builder.branch(end_bb)

        self.builder.position_at_start(end_bb)

    def _compile_async_function(self, node):
        """Compile async function as a regular function (no concurrency in native code)."""
        sync_fn = ast.FunctionDef(node.name, node.params, node.return_type, node.body, node.line)
        if node.name not in self.functions:
            self._register_function(sync_fn)
        self._compile_function_def(sync_fn)

    def _compile_super_call(self, node):
        """Compile Super.method(args) or Super(args) for constructor."""
        # Find parent class in current context
        current_class = None
        for cn, cd in self.class_defs.items():
            for item in cd.body:
                if isinstance(item, ast.FunctionDef):
                    fname = f"{cn}_{item.name}"
                    if fname in self.functions and self.functions[fname][0] == self.func:
                        current_class = cn
                        break
            if current_class:
                break
        if not current_class:
            return
        parent = getattr(self.class_defs.get(current_class), 'parent', None)
        if not parent:
            return
        method = node.method_name or 'init'
        parent_fn_name = f"{parent}_{method}"
        if parent_fn_name in self.functions:
            func = self.functions[parent_fn_name][0]
            call_args = []
            # Pass self (first argument of current function)
            if self.func.args:
                call_args.append(self.func.args[0])
            for a in node.arguments:
                call_args.append(self._compile_expr(a))
            final = []
            for i, a in enumerate(call_args):
                if i < len(func.args):
                    a = self._coerce_to_type(a, func.args[i].type)
                final.append(a)
            self.builder.call(func, final)

    def _compile_super_call_expr(self, node):
        """Super.method(args) as expression — returns the call result."""
        current_class = None
        for cn, cd in self.class_defs.items():
            for item in cd.body:
                if isinstance(item, ast.FunctionDef):
                    fname = f"{cn}_{item.name}"
                    if fname in self.functions and self.functions[fname][0] == self.func:
                        current_class = cn
                        break
            if current_class:
                break
        if not current_class:
            return ir.Constant(self.i64, 0)
        parent = getattr(self.class_defs.get(current_class), 'parent', None)
        if not parent:
            return ir.Constant(self.i64, 0)
        method = node.method_name or 'init'
        parent_fn_name = f"{parent}_{method}"
        if parent_fn_name in self.functions:
            func = self.functions[parent_fn_name][0]
            call_args = []
            if self.func.args:
                call_args.append(self.func.args[0])
            for a in node.arguments:
                call_args.append(self._compile_expr(a))
            final = []
            for i, a in enumerate(call_args):
                if i < len(func.args):
                    a = self._coerce_to_type(a, func.args[i].type)
                final.append(a)
            return self.builder.call(func, final)
        return ir.Constant(self.i64, 0)

    def _compile_module_def(self, node):
        """Compile Module body — functions prefixed with ModuleName_."""
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                fn_name = f"{node.name}_{item.name}"
                if fn_name not in self.functions:
                    prefixed = ast.FunctionDef(
                        fn_name, item.params,
                        item.return_type, item.body, item.line
                    )
                    self._register_function(prefixed)
                self._compile_function_def(ast.FunctionDef(
                    fn_name, item.params, item.return_type, item.body, item.line
                ))
            elif isinstance(item, ast.VarDeclaration):
                self._compile_var_decl(item)
                if item.name in self.variables:
                    self.variables[f"{node.name}_{item.name}"] = self.variables[item.name]
                    self.var_types[f"{node.name}_{item.name}"] = self.var_types.get(item.name, 'int')
            elif isinstance(item, ast.ExportStatement):
                pass
            elif not self.builder.block.is_terminated:
                self._compile_stmt(item)

    def _compile_module_access(self, node):
        """Compile Module::function() or Module::variable as statement."""
        if node.arguments is not None:
            fn_name = f"{node.module_name}_{node.member_name}"
            if fn_name in self.functions:
                func = self.functions[fn_name][0]
                args = [self._compile_expr(a) for a in node.arguments]
                final = []
                for i, a in enumerate(args):
                    if i < len(func.args):
                        a = self._coerce_to_type(a, func.args[i].type)
                    final.append(a)
                return self.builder.call(func, final)
        else:
            var_name = f"{node.module_name}_{node.member_name}"
            if var_name in self.variables:
                return self.builder.load(self.variables[var_name])
        return ir.Constant(self.i64, 0)

    def _compile_module_access_expr(self, node):
        """Module::member as expression."""
        return self._compile_module_access(node)

    def _compile_yield(self, node):
        """Yield — in native code, stores value in a generator state variable.
        For native compilation, yield is compiled as a return (simplified)."""
        if node.value:
            val = self._compile_expr(node.value)
            self.builder.ret(val)
        else:
            if self.func.return_value.type == self.void:
                self.builder.ret_void()
            else:
                self.builder.ret(ir.Constant(self.i64, 0))

    def _compile_destructure(self, node):
        """Create [a, b, c] equal to someList — destructure a list."""
        list_val = self._compile_expr(node.value)
        for i, name in enumerate(node.names):
            idx = ir.Constant(self.i64, i)
            elem = self.builder.call(self.rt_list_get_int, [list_val, idx])
            if name not in self.variables:
                a = self.builder.alloca(self.i64, name=name)
                self.variables[name] = a
                self.var_types[name] = 'int'
            self.builder.store(elem, self.variables[name])

    def _compile_chained_comparison(self, node):
        """a < b < c → (a < b) and (b < c)."""
        result = None
        for i in range(len(node.operators)):
            left = self._compile_expr(node.operands[i])
            right = self._compile_expr(node.operands[i + 1])
            cmp_op = node.operators[i]
            op_map = {'<': '<', '>': '>', '<=': '<=', '>=': '>=', '==': '==', '!=': '!='}
            llvm_op = op_map.get(cmp_op, '==')
            if isinstance(left.type, ir.DoubleType) or isinstance(right.type, ir.DoubleType):
                if not isinstance(left.type, ir.DoubleType):
                    left = self.builder.sitofp(left, self.f64)
                if not isinstance(right.type, ir.DoubleType):
                    right = self.builder.sitofp(right, self.f64)
                cmp_val = self.builder.fcmp_ordered(llvm_op, left, right)
            else:
                if isinstance(left.type, ir.IntType) and isinstance(right.type, ir.IntType):
                    if left.type.width != right.type.width:
                        left = self.builder.sext(left, self.i64) if left.type.width < 64 else left
                        right = self.builder.sext(right, self.i64) if right.type.width < 64 else right
                cmp_val = self.builder.icmp_signed(llvm_op, left, right)
            if result is None:
                result = cmp_val
            else:
                result = self.builder.and_(result, cmp_val)
        return result or ir.Constant(self.i1, 0)

    # ─── v5.2 Phase 1: Spawn / Parallel / Breakpoint / FFI ───

    def _compile_spawn(self, node):
        """Spawn task_name calling func(args) — runs function on a new OS thread.
        
        Generates a void(*)(void) trampoline that captures args, then calls
        epl_spawn_task() which creates a new thread. The thread handle is stored
        as an i64 variable so the user can later wait on it.
        """
        # Step 1: Build the trampoline — a no-arg function that calls the target
        self._spawn_counter += 1
        tramp_name = f"_epl_spawn_trampoline_{self._spawn_counter}"
        tramp_ty = ir.FunctionType(self.void, [])
        tramp_fn = ir.Function(self.module, tramp_ty, name=tramp_name)
        tramp_block = tramp_fn.append_basic_block(name="entry")

        # Save current builder state
        prev_builder = self.builder
        prev_func = self.func
        prev_vars = self.variables.copy()
        prev_var_types = self.var_types.copy()

        self.builder = ir.IRBuilder(tramp_block)
        self.func = tramp_fn

        # Step 2: Compile the expression (function call) inside the trampoline
        if isinstance(node.expression, ast.FunctionCall):
            self._compile_function_call(node.expression)
        else:
            self._compile_expr(node.expression)

        # Make sure trampoline returns void
        if not self.builder.block.is_terminated:
            self.builder.ret_void()

        # Restore builder state
        self.builder = prev_builder
        self.func = prev_func
        self.variables = prev_vars
        self.var_types = prev_var_types

        # Step 3: Call epl_spawn_task with the trampoline function pointer
        func_ptr = self.builder.bitcast(tramp_fn, self.i8_ptr)
        handle = self.builder.call(self.rt_spawn_task, [func_ptr])

        # Step 4: Store handle as variable
        if node.var_name not in self.variables:
            a = self.builder.alloca(self.i64, name=node.var_name)
            self.variables[node.var_name] = a
            self.var_types[node.var_name] = 'int'
        self.builder.store(handle, self.variables[node.var_name])

    def _compile_parallel_for_each(self, node):
        """Parallel For Each — compiles as sequential for-each with per-iteration
        function calls (same pattern as async compiled as sync).
        
        A full work-stealing thread pool is beyond current scope, but the
        iteration body is compiled correctly so it runs natively. When a thread
        pool scheduler is added to runtime.c, this codegen will need only a
        small change to dispatch work items.
        """
        # Compile as regular ForEach for correctness
        sync_node = ast.ForEachLoop(node.var_name, node.iterable, node.body, node.line)
        self._compile_for_each(sync_node)

    def _compile_breakpoint(self, node):
        """Breakpoint — emit a debug trap instruction.
        
        If a condition is present, only trap when condition is true.
        In release builds (opt >= 2), breakpoints are skipped.
        """
        if self.opt_level >= 2:
            return  # Strip breakpoints in optimized builds

        if node.condition is not None:
            cond = self._compile_expr(node.condition)
            cond_bool = self._to_bool(cond)
            then_bb = self.func.append_basic_block("bp_then")
            merge_bb = self.func.append_basic_block("bp_merge")
            self.builder.cbranch(cond_bool, then_bb, merge_bb)

            self.builder.position_at_start(then_bb)
            self.builder.call(self.rt_debug_trap, [])
            self.builder.branch(merge_bb)

            self.builder.position_at_start(merge_bb)
        else:
            self.builder.call(self.rt_debug_trap, [])

    def _compile_load_library(self, node):
        """Load library "path" as name — opens a shared library via dlopen.
        
        Stores the library handle as a pointer variable.
        """
        path_str = self._make_global_string(node.path, f"_lib_path_{node.alias}")
        path_ptr = self._get_string_ptr(path_str)
        handle = self.builder.call(self.rt_dlopen, [path_ptr])

        # Store as pointer variable
        if node.alias not in self.variables:
            a = self.builder.alloca(self.i8_ptr, name=node.alias)
            self.variables[node.alias] = a
            self.var_types[node.alias] = 'pointer'
        self.builder.store(handle, self.variables[node.alias])
        self._lib_handles[node.path] = node.alias

    def _compile_external_function_def(self, node):
        """External function name from "lib" takes (...) returns type
        
        Opens the library (or reuses cached handle), resolves the symbol,
        and registers a wrapper function that calls through the resolved pointer.
        """
        # Step 1: Open or reuse library handle
        lib_var = self._lib_handles.get(node.library)
        if lib_var and lib_var in self.variables:
            lib_handle = self.builder.load(self.variables[lib_var])
        else:
            lib_str = self._make_global_string(node.library, f"_lib_{_mangle_name(node.library)}")
            lib_ptr = self._get_string_ptr(lib_str)
            lib_handle = self.builder.call(self.rt_dlopen, [lib_ptr])
            # Cache the handle
            cache_name = f"__ffi_lib_{_mangle_name(node.library)}"
            if cache_name not in self.variables:
                a = self.builder.alloca(self.i8_ptr, name=cache_name)
                self.variables[cache_name] = a
                self.var_types[cache_name] = 'pointer'
            self.builder.store(lib_handle, self.variables[cache_name])
            self._lib_handles[node.library] = cache_name

        # Step 2: Resolve the symbol
        sym_str = self._make_global_string(node.name, f"_sym_{node.name}")
        sym_ptr = self._get_string_ptr(sym_str)
        func_ptr = self.builder.call(self.rt_dlsym, [lib_handle, sym_ptr])

        # Step 3: Store the function pointer
        epl_name = node.alias or node.name
        if epl_name not in self.variables:
            a = self.builder.alloca(self.i8_ptr, name=epl_name)
            self.variables[epl_name] = a
            self.var_types[epl_name] = 'ffi_func'
        self.builder.store(func_ptr, self.variables[epl_name])
