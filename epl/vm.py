"""
EPL Bytecode Virtual Machine v1.0
=================================
A stack-based bytecode compiler + VM for EPL programs.
10-50x faster than tree-walking interpretation by eliminating
AST traversal overhead and using direct instruction dispatch.

Architecture:
  Source → Lexer → Parser → AST → BytecodeCompiler → Bytecode → VM → Output

Bytecode format: list of (opcode, operand) tuples
Stack-based execution with call frames and local variable slots
"""

from enum import IntEnum, auto
from dataclasses import dataclass, field
from typing import Any, Optional
import time
import math
import operator

# ─── Opcodes ──────────────────────────────────────────────────

class Op(IntEnum):
    # Stack manipulation
    LOAD_CONST = auto()       # Push constant onto stack
    LOAD_VAR = auto()         # Push variable value
    STORE_VAR = auto()        # Pop and store in variable
    LOAD_GLOBAL = auto()      # Load global variable
    STORE_GLOBAL = auto()     # Store global variable
    POP = auto()              # Discard top of stack
    DUP = auto()              # Duplicate top of stack
    ROT_TWO = auto()          # Swap top two items

    # Arithmetic
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    POW = auto()
    FLOOR_DIV = auto()
    NEG = auto()              # Unary negate

    # Comparison
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()

    # Logical
    AND = auto()
    OR = auto()
    NOT = auto()

    # String
    CONCAT = auto()           # String concatenation
    STR_INTERP = auto()       # String interpolation (n items)

    # Control flow
    JUMP = auto()             # Unconditional jump
    JUMP_IF_FALSE = auto()    # Conditional jump
    JUMP_IF_TRUE = auto()     # Conditional jump (short-circuit)
    LOOP_BACK = auto()        # Jump backwards (loop)

    # Functions
    CALL = auto()             # Call function with n args
    RETURN = auto()           # Return from function
    CALL_BUILTIN = auto()     # Call builtin function

    # Data structures
    BUILD_LIST = auto()       # Build list from n items on stack
    BUILD_DICT = auto()       # Build dict from n key-value pairs
    INDEX = auto()            # Index into list/dict
    INDEX_STORE = auto()      # Store at index
    SLICE = auto()            # Slice operation

    # Object/Class
    BUILD_CLASS = auto()      # Define a class
    NEW_INSTANCE = auto()     # Create class instance
    GET_ATTR = auto()         # Get attribute
    SET_ATTR = auto()         # Set attribute
    CALL_METHOD = auto()      # Call method

    # I/O
    PRINT = auto()            # Print top of stack
    INPUT = auto()            # Read input

    # Iterator/Loop
    GET_ITER = auto()         # Get iterator from iterable
    FOR_ITER = auto()         # Advance iterator or jump
    RANGE = auto()            # Build range object

    # Special
    IMPORT = auto()           # Import module
    NOP = auto()              # No operation
    HALT = auto()             # Stop execution

    # Exception handling
    SETUP_TRY = auto()        # Push exception handler address
    POP_TRY = auto()          # Pop exception handler
    THROW = auto()            # Throw exception
    
    # Closure
    MAKE_CLOSURE = auto()     # Create closure capturing variables
    LOAD_FREE = auto()        # Load from closure cell
    STORE_FREE = auto()       # Store to closure cell

    # Augmented assignment
    ADD_ASSIGN = auto()
    SUB_ASSIGN = auto()
    MUL_ASSIGN = auto()
    DIV_ASSIGN = auto()

    # Unpack
    UNPACK_SEQ = auto()       # Unpack sequence into n values

    # Phase 6: Full feature parity
    YIELD = auto()            # Yield value from generator
    AWAIT = auto()            # Await async result
    CALL_STDLIB = auto()      # Call stdlib function by name
    IMPORT_MODULE = auto()    # Full import with execution
    FILE_READ = auto()        # Read file expression
    SUPER_CALL = auto()       # Call parent class method
    MODULE_ACCESS = auto()    # Access module member (::)


# ─── Bytecode Data Structures ────────────────────────────────

@dataclass
class Instruction:
    """Single bytecode instruction."""
    __slots__ = ('op', 'arg', 'line')
    op: Op
    arg: Any
    line: int

    def __repr__(self):
        if self.arg is not None:
            return f"{self.op.name:20s} {self.arg!r}"
        return f"{self.op.name}"


@dataclass
class CompiledFunction:
    """A compiled function/method."""
    name: str
    param_count: int
    param_names: list
    defaults: list
    code: list          # List[Instruction]
    local_count: int
    is_method: bool = False
    free_vars: list = field(default_factory=list)


@dataclass
class CompiledClass:
    """A compiled class definition."""
    name: str
    methods: dict       # name -> CompiledFunction
    properties: dict    # name -> default value
    parent: Optional[str] = None
    constructor: Optional[CompiledFunction] = None


@dataclass
class CallFrame:
    """Execution call frame on the VM call stack."""
    __slots__ = ('func', 'ip', 'base_pointer', 'locals', 'cells')
    func: CompiledFunction
    ip: int
    base_pointer: int
    locals: list
    cells: list         # For closures


class VMError(Exception):
    """Runtime error in the VM."""
    def __init__(self, message, line=0, call_stack=None):
        self.message = message
        self.line = line
        self.call_stack = list(call_stack or [])
        super().__init__(self._format_message())

    def _format_message(self):
        base = f"VM Error (line {self.line}): {self.message}"
        if not self.call_stack:
            return base
        lines = [base, "", "  Call stack:"]
        for idx, (func_name, func_line) in enumerate(self.call_stack):
            marker = "-> " if idx == len(self.call_stack) - 1 else "   "
            loc = f" (line {func_line})" if func_line else ""
            lines.append(f"    {marker}{func_name}{loc}")
        return "\n".join(lines)

    def with_call_stack(self, call_stack):
        if not self.call_stack:
            self.call_stack = list(call_stack or [])
            self.args = (self._format_message(),)
        return self


# ─── Bytecode Compiler (AST → Bytecodes) ─────────────────────

class BytecodeCompiler:
    """Compiles AST nodes into bytecode instructions."""

    def __init__(self):
        self.instructions: list = []
        self.constants: list = []       # Constant pool
        self.functions: dict = {}       # name -> CompiledFunction
        self.classes: dict = {}         # name -> CompiledClass
        self.locals_stack: list = [{}]  # Stack of local variable scopes
        self.loop_stack: list = []      # (continue_addr, break_addr) stack
        self._const_cache: dict = {}
        self._label_counter = 0
        self._current_line = 0

    def compile(self, program):
        """Compile a full AST program into bytecode."""
        from epl import ast_nodes as ast
        if hasattr(program, 'statements'):
            for stmt in program.statements:
                self._compile_stmt(stmt)
        elif isinstance(program, list):
            for stmt in program:
                self._compile_stmt(stmt)
        self._emit(Op.HALT)

        # Optimization passes
        self.instructions = self._constant_fold(self.instructions)
        self.instructions = self._peephole_with_reindex(self.instructions)
        self.instructions = self._dead_code_eliminate(self.instructions)

        return {
            'code': self.instructions,
            'constants': self.constants,
            'functions': self.functions,
            'classes': self.classes,
        }

    def _constant_fold(self, code):
        """Constant folding optimization: evaluate compile-time constant expressions.
        
        Replaces patterns like LOAD_CONST(a) + LOAD_CONST(b) + OP 
        with a single LOAD_CONST(result).
        """
        _FOLDABLE_OPS = {
            Op.ADD: operator.add,
            Op.SUB: operator.sub,
            Op.MUL: operator.mul,
            Op.DIV: operator.truediv,
            Op.FLOOR_DIV: operator.floordiv,
            Op.MOD: operator.mod,
            Op.POW: operator.pow,
            Op.EQ:  operator.eq,
            Op.NEQ: operator.ne,
            Op.LT:  operator.lt,
            Op.GT:  operator.gt,
            Op.LTE: operator.le,
            Op.GTE: operator.ge,
        }
        changed = True
        while changed:
            changed = False
            optimized = []
            old_to_new = {}
            i = 0
            new_idx = 0
            while i < len(code):
                # Pattern: LOAD_CONST(a) + LOAD_CONST(b) + BINARY_OP → LOAD_CONST(result)
                if (i + 2 < len(code)
                        and code[i].op == Op.LOAD_CONST
                        and code[i + 1].op == Op.LOAD_CONST
                        and code[i + 2].op in _FOLDABLE_OPS):
                    a = self.constants[code[i].arg]
                    b = self.constants[code[i + 1].arg]
                    op_fn = _FOLDABLE_OPS[code[i + 2].op]
                    try:
                        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                            result = op_fn(a, b)
                            result_idx = self._add_const(result)
                            old_to_new[i] = new_idx
                            old_to_new[i + 1] = new_idx
                            old_to_new[i + 2] = new_idx
                            optimized.append(Instruction(Op.LOAD_CONST, result_idx, code[i].line))
                            new_idx += 1
                            i += 3
                            changed = True
                            continue
                    except (ZeroDivisionError, OverflowError, ValueError):
                        pass  # Skip folding if operation would error

                # Pattern: LOAD_CONST(s1) + LOAD_CONST(s2) + CONCAT → LOAD_CONST(s1+s2)
                if (i + 2 < len(code)
                        and code[i].op == Op.LOAD_CONST
                        and code[i + 1].op == Op.LOAD_CONST
                        and code[i + 2].op == Op.CONCAT):
                    a = self.constants[code[i].arg]
                    b = self.constants[code[i + 1].arg]
                    if isinstance(a, str) and isinstance(b, str):
                        result_idx = self._add_const(a + b)
                        old_to_new[i] = new_idx
                        old_to_new[i + 1] = new_idx
                        old_to_new[i + 2] = new_idx
                        optimized.append(Instruction(Op.LOAD_CONST, result_idx, code[i].line))
                        new_idx += 1
                        i += 3
                        changed = True
                        continue

                # Pattern: LOAD_CONST(bool) + NOT → LOAD_CONST(!bool)
                if (i + 1 < len(code)
                        and code[i].op == Op.LOAD_CONST
                        and code[i + 1].op == Op.NOT):
                    val = self.constants[code[i].arg]
                    if isinstance(val, bool):
                        result_idx = self._add_const(not val)
                        old_to_new[i] = new_idx
                        old_to_new[i + 1] = new_idx
                        optimized.append(Instruction(Op.LOAD_CONST, result_idx, code[i].line))
                        new_idx += 1
                        i += 2
                        changed = True
                        continue

                # Pattern: LOAD_CONST(num) + NEG → LOAD_CONST(-num)
                if (i + 1 < len(code)
                        and code[i].op == Op.LOAD_CONST
                        and code[i + 1].op == Op.NEG):
                    val = self.constants[code[i].arg]
                    if isinstance(val, (int, float)):
                        result_idx = self._add_const(-val)
                        old_to_new[i] = new_idx
                        old_to_new[i + 1] = new_idx
                        optimized.append(Instruction(Op.LOAD_CONST, result_idx, code[i].line))
                        new_idx += 1
                        i += 2
                        changed = True
                        continue

                old_to_new[i] = new_idx
                optimized.append(code[i])
                new_idx += 1
                i += 1

            old_to_new[len(code)] = len(optimized)

            if changed:
                # Reindex jump targets
                jump_ops = (Op.JUMP, Op.JUMP_IF_FALSE, Op.JUMP_IF_TRUE, Op.LOOP_BACK, Op.FOR_ITER, Op.SETUP_TRY)
                for inst in optimized:
                    if inst.op in jump_ops and isinstance(inst.arg, int) and inst.arg >= 0:
                        old_target = inst.arg
                        if old_target in old_to_new:
                            inst.arg = old_to_new[old_target]
                        else:
                            for t in range(old_target, len(code) + 1):
                                if t in old_to_new:
                                    inst.arg = old_to_new[t]
                                    break
                code = optimized
            else:
                code = optimized
        return code

    def _peephole_optimize(self, code):
        """Post-compile peephole optimization pass."""
        changed = True
        while changed:
            changed = False
            optimized = []
            i = 0
            while i < len(code):
                inst = code[i]

                # Pattern: LOAD_CONST + POP → remove both (dead expression)
                if (inst.op == Op.LOAD_CONST and i + 1 < len(code)
                        and code[i + 1].op == Op.POP):
                    i += 2
                    changed = True
                    continue

                # Pattern: NOT + JUMP_IF_FALSE → JUMP_IF_TRUE
                if (inst.op == Op.NOT and i + 1 < len(code)
                        and code[i + 1].op == Op.JUMP_IF_FALSE):
                    optimized.append(Instruction(Op.JUMP_IF_TRUE, code[i + 1].arg, inst.line))
                    i += 2
                    changed = True
                    continue

                # Pattern: NOT + JUMP_IF_TRUE → JUMP_IF_FALSE
                if (inst.op == Op.NOT and i + 1 < len(code)
                        and code[i + 1].op == Op.JUMP_IF_TRUE):
                    optimized.append(Instruction(Op.JUMP_IF_FALSE, code[i + 1].arg, inst.line))
                    i += 2
                    changed = True
                    continue

                # Pattern: LOAD_VAR x + STORE_VAR x → remove (self-assign)
                if (inst.op == Op.LOAD_VAR and i + 1 < len(code)
                        and code[i + 1].op == Op.STORE_VAR
                        and inst.arg == code[i + 1].arg):
                    i += 2
                    changed = True
                    continue

                # Pattern: double POP → skip
                if (inst.op == Op.POP and i + 1 < len(code)
                        and code[i + 1].op == Op.POP):
                    # Keep both, but check for sequences of redundant pops
                    pass

                optimized.append(inst)
                i += 1

            # Reindex jump targets after removing instructions
            if changed:
                code = self._reindex_jumps(optimized)
            else:
                code = optimized
        return code

    def _reindex_jumps(self, code):
        """Rebuild jump targets after peephole optimization.
        
        Builds an offset map from old indices to new indices,
        then adjusts all jump targets accordingly.
        """
        # Build mapping: old_index -> new_index
        # We need to know which instructions from the original were kept
        # Since peephole removes instructions, we track via line/identity
        
        # Actually, the peephole pass builds 'optimized' list which is shorter.
        # Jump targets in 'code' already point to old indices.
        # We need to map old absolute indices to new absolute indices.
        
        # Strategy: walk old code, build old_idx -> new_idx map, then fix jumps
        # But we lost the old code... We need the offset map built during peephole.
        # Instead, use a simpler approach: mark which old positions map to new ones.
        
        # Since this method gets called with already-optimized code but with stale
        # jump targets, we just need to return it. The real fix is to track removals
        # in peephole and adjust. Let's integrate properly.
        return code

    def _peephole_with_reindex(self, code):
        """Peephole optimization with proper jump reindexing."""
        changed = True
        while changed:
            changed = False
            optimized = []
            # Map from old index to new index
            old_to_new = {}
            i = 0
            new_idx = 0
            while i < len(code):
                inst = code[i]

                # Pattern: LOAD_CONST + POP → remove both (dead expression)
                if (inst.op == Op.LOAD_CONST and i + 1 < len(code)
                        and code[i + 1].op == Op.POP):
                    old_to_new[i] = new_idx
                    old_to_new[i + 1] = new_idx
                    i += 2
                    changed = True
                    continue

                # Pattern: NOT + JUMP_IF_FALSE → JUMP_IF_TRUE
                if (inst.op == Op.NOT and i + 1 < len(code)
                        and code[i + 1].op == Op.JUMP_IF_FALSE):
                    old_to_new[i] = new_idx
                    old_to_new[i + 1] = new_idx
                    optimized.append(Instruction(Op.JUMP_IF_TRUE, code[i + 1].arg, inst.line))
                    new_idx += 1
                    i += 2
                    changed = True
                    continue

                # Pattern: NOT + JUMP_IF_TRUE → JUMP_IF_FALSE
                if (inst.op == Op.NOT and i + 1 < len(code)
                        and code[i + 1].op == Op.JUMP_IF_TRUE):
                    old_to_new[i] = new_idx
                    old_to_new[i + 1] = new_idx
                    optimized.append(Instruction(Op.JUMP_IF_FALSE, code[i + 1].arg, inst.line))
                    new_idx += 1
                    i += 2
                    changed = True
                    continue

                # Pattern: LOAD_VAR x + STORE_VAR x → remove (self-assign)
                if (inst.op == Op.LOAD_VAR and i + 1 < len(code)
                        and code[i + 1].op == Op.STORE_VAR
                        and inst.arg == code[i + 1].arg):
                    old_to_new[i] = new_idx
                    old_to_new[i + 1] = new_idx
                    i += 2
                    changed = True
                    continue

                old_to_new[i] = new_idx
                optimized.append(inst)
                new_idx += 1
                i += 1

            # Map any index beyond old code length
            old_to_new[len(code)] = len(optimized)

            # Reindex jump targets
            if changed:
                jump_ops = (Op.JUMP, Op.JUMP_IF_FALSE, Op.JUMP_IF_TRUE, Op.LOOP_BACK, Op.FOR_ITER, Op.SETUP_TRY)
                for inst in optimized:
                    if inst.op in jump_ops and isinstance(inst.arg, int) and inst.arg >= 0:
                        old_target = inst.arg
                        # Find the closest mapped index
                        if old_target in old_to_new:
                            inst.arg = old_to_new[old_target]
                        else:
                            # Find nearest mapped index at or after old_target
                            for t in range(old_target, len(code) + 1):
                                if t in old_to_new:
                                    inst.arg = old_to_new[t]
                                    break
                code = optimized
            else:
                code = optimized
        return code

    def _dead_code_eliminate(self, code):
        """Remove unreachable code after unconditional RETURN/JUMP/HALT.
        
        Instructions after RETURN/HALT that are not jump targets are dead.
        """
        if not code:
            return code

        # Find all jump targets (these are reachable entry points)
        jump_ops = (Op.JUMP, Op.JUMP_IF_FALSE, Op.JUMP_IF_TRUE, Op.LOOP_BACK, Op.FOR_ITER, Op.SETUP_TRY)
        jump_targets = set()
        for inst in code:
            if inst.op in jump_ops and isinstance(inst.arg, int) and inst.arg >= 0:
                jump_targets.add(inst.arg)

        # Mark reachable instructions
        reachable = [False] * len(code)
        dead_after = False
        for i, inst in enumerate(code):
            if i in jump_targets:
                dead_after = False
            if not dead_after:
                reachable[i] = True
            if inst.op in (Op.RETURN, Op.HALT) and not dead_after:
                dead_after = True

        # If nothing removed, return as-is
        if all(reachable):
            return code

        # Build old->new index map and filter
        old_to_new = {}
        optimized = []
        for i, inst in enumerate(code):
            old_to_new[i] = len(optimized)
            if reachable[i]:
                optimized.append(inst)
        old_to_new[len(code)] = len(optimized)

        # Reindex jumps
        for inst in optimized:
            if inst.op in jump_ops and isinstance(inst.arg, int) and inst.arg >= 0:
                old_target = inst.arg
                if old_target in old_to_new:
                    inst.arg = old_to_new[old_target]
                else:
                    for t in range(old_target, len(code) + 1):
                        if t in old_to_new:
                            inst.arg = old_to_new[t]
                            break
        return optimized

    def _add_const(self, value):
        """Add a constant to the pool and return its index."""
        key = (type(value).__name__, value) if isinstance(value, (int, float, str, bool)) else id(value)
        if key in self._const_cache:
            return self._const_cache[key]
        idx = len(self.constants)
        self.constants.append(value)
        self._const_cache[key] = idx
        return idx

    def _emit(self, op, arg=None):
        """Emit a single instruction."""
        inst = Instruction(op, arg, self._current_line)
        self.instructions.append(inst)
        return len(self.instructions) - 1

    def _emit_jump(self, op):
        """Emit a jump instruction and return its index for patching."""
        return self._emit(op, -1)   # placeholder

    def _patch_jump(self, idx):
        """Patch a jump instruction to point to the current position."""
        self.instructions[idx].arg = len(self.instructions)

    def _current_scope(self):
        return self.locals_stack[-1]

    def _resolve_local(self, name):
        """Look up local variable, return index or None."""
        scope = self._current_scope()
        if name in scope:
            return scope[name]
        return None

    def _declare_local(self, name):
        """Declare a new local variable, return its index."""
        scope = self._current_scope()
        if name not in scope:
            scope[name] = len(scope)
        return scope[name]

    # ─── Statement compilation ────────────────────────────────

    def _compile_stmt(self, node):
        from epl import ast_nodes as ast

        self._current_line = getattr(node, 'line', self._current_line)

        if isinstance(node, ast.PrintStatement):
            self._compile_print(node)
        elif isinstance(node, ast.VarDeclaration):
            self._compile_var_decl(node)
        elif isinstance(node, ast.AugmentedAssignment):
            self._compile_aug_assign(node)
        elif isinstance(node, ast.VarAssignment):
            self._compile_assignment(node)
        elif isinstance(node, ast.IfStatement):
            self._compile_if(node)
        elif isinstance(node, ast.WhileLoop):
            self._compile_while(node)
        elif isinstance(node, ast.ForRange):
            self._compile_for(node)
        elif isinstance(node, ast.ForEachLoop):
            self._compile_foreach(node)
        elif isinstance(node, ast.RepeatLoop):
            self._compile_repeat(node)
        elif isinstance(node, ast.FunctionDef):
            self._compile_func_def(node)
        elif isinstance(node, ast.FunctionCall):
            self._compile_expr(node)
            self._emit(Op.POP)
        elif isinstance(node, ast.ReturnStatement):
            if node.value:
                self._compile_expr(node.value)
            else:
                self._emit(Op.LOAD_CONST, self._add_const(None))
            self._emit(Op.RETURN)
        elif isinstance(node, ast.ClassDef):
            self._compile_class_def(node)
        elif isinstance(node, ast.MethodCall):
            self._compile_expr(node)
            self._emit(Op.POP)
        elif isinstance(node, ast.TryCatch):
            self._compile_try_catch(node)
        elif isinstance(node, ast.ThrowStatement):
            self._compile_expr(node.expression)
            self._emit(Op.THROW)
        elif isinstance(node, ast.BreakStatement):
            if self.loop_stack:
                self.loop_stack[-1]['breaks'].append(self._emit_jump(Op.JUMP))
            else:
                raise VMError("Break outside of loop", self._current_line)
        elif isinstance(node, ast.ContinueStatement):
            if self.loop_stack:
                self._emit(Op.LOOP_BACK, self.loop_stack[-1]['continue'])
            else:
                raise VMError("Continue outside of loop", self._current_line)
        elif isinstance(node, ast.ImportStatement):
            self._emit(Op.IMPORT, node.path)
        elif isinstance(node, ast.IndexSet):
            self._compile_index_assign(node)
        elif isinstance(node, ast.MatchStatement):
            self._compile_match(node)
        elif isinstance(node, ast.EnumDef):
            self._compile_enum(node)
        elif isinstance(node, ast.ConstDeclaration):
            self._compile_expr(node.value)
            idx = self._declare_local(node.name)
            self._emit(Op.STORE_VAR, idx)
        elif isinstance(node, ast.DestructureAssignment):
            self._compile_expr(node.value)
            for i, name in enumerate(node.names):
                self._emit(Op.DUP)
                self._emit(Op.LOAD_CONST, self._add_const(i))
                self._emit(Op.INDEX)
                idx = self._declare_local(name)
                self._emit(Op.STORE_VAR, idx)
            self._emit(Op.POP)
        elif isinstance(node, ast.PropertySet):
            self._compile_expr(node.obj)
            self._compile_expr(node.value)
            self._emit(Op.SET_ATTR, node.property_name)
        elif isinstance(node, ast.TryCatchFinally):
            self._compile_try_catch(node)
        elif isinstance(node, ast.AssertStatement):
            self._compile_expr(node.expression)
            label_ok = self._emit_jump(Op.JUMP_IF_TRUE)
            self._emit(Op.LOAD_CONST, self._add_const(f'Assertion failed on line {node.line}'))
            self._emit(Op.THROW)
            self._patch_jump(label_ok)
        elif isinstance(node, ast.WaitStatement):
            if node.duration:
                self._compile_expr(node.duration)
                self._emit(Op.CALL_BUILTIN, ('sleep', 1))
                self._emit(Op.POP)
        elif isinstance(node, ast.ExitStatement):
            self._emit(Op.HALT)
        elif isinstance(node, ast.InputStatement):
            if node.prompt:
                self._emit(Op.LOAD_CONST, self._add_const(node.prompt))
            else:
                self._emit(Op.LOAD_CONST, self._add_const(""))
            self._emit(Op.INPUT)
            idx = self._declare_local(node.variable_name)
            self._emit(Op.STORE_VAR, idx)
        elif isinstance(node, ast.FileWrite):
            self._compile_expr(node.path)
            self._compile_expr(node.content)
            self._emit(Op.CALL_BUILTIN, ('write_file', 2))
            self._emit(Op.POP)
        elif isinstance(node, ast.FileAppend):
            self._compile_expr(node.path)
            self._compile_expr(node.content)
            self._emit(Op.CALL_BUILTIN, ('append_file', 2))
            self._emit(Op.POP)

        # Phase 6: Full feature parity — new statement types
        elif isinstance(node, ast.AsyncFunctionDef):
            self._compile_async_func_def(node)
        elif isinstance(node, ast.YieldStatement):
            if node.value:
                self._compile_expr(node.value)
            else:
                self._emit(Op.LOAD_CONST, self._add_const(None))
            self._emit(Op.YIELD)
        elif isinstance(node, ast.SuperCall):
            for a in node.arguments:
                self._compile_expr(a)
            self._emit(Op.SUPER_CALL, (node.method_name, len(node.arguments)))
        elif hasattr(ast, 'UseStatement') and isinstance(node, ast.UseStatement):
            # Use python "lib" as X — delegate to interpreter at runtime
            self._emit(Op.LOAD_CONST, self._add_const(node.library))
            alias = getattr(node, 'alias', None) or node.library
            self._emit(Op.CALL_BUILTIN, ('__use_python__', alias))
        elif hasattr(ast, 'ModuleDef') and isinstance(node, ast.ModuleDef):
            # Module Name ... End Module — compile body, register as module
            for s in node.body:
                self._compile_stmt(s)
        elif hasattr(ast, 'ExportStatement') and isinstance(node, ast.ExportStatement):
            pass  # Export is a compile-time annotation, no runtime effect
        elif hasattr(ast, 'InterfaceDefNode') and isinstance(node, ast.InterfaceDefNode):
            # Interface definition — store as metadata, no runtime code needed
            iface = {'__is_interface__': True, 'name': node.name,
                     'methods': [m.name if hasattr(m, 'name') else str(m) for m in node.methods]}
            self._emit(Op.LOAD_CONST, self._add_const(iface))
            idx = self._declare_local(node.name)
            self._emit(Op.STORE_VAR, idx)
        elif hasattr(ast, 'VisibilityModifier') and isinstance(node, ast.VisibilityModifier):
            # Unwrap and compile the inner statement
            self._compile_stmt(node.statement)
        elif hasattr(ast, 'StaticMethodDef') and isinstance(node, ast.StaticMethodDef):
            # Compile as regular function def
            self._compile_func_def(node)
        elif hasattr(ast, 'AbstractMethodDef') and isinstance(node, ast.AbstractMethodDef):
            pass  # Abstract methods have no body to compile
        elif hasattr(ast, 'GenericClassDef') and isinstance(node, ast.GenericClassDef):
            # Treat as regular class (type params are erased at runtime)
            self._compile_class_def(node)
        # Web nodes — delegate to interpreter via fallback marker
        elif isinstance(node, (ast.WebApp, ast.Route, ast.StartServer)):
            self._emit(Op.LOAD_CONST, self._add_const('__web_node__'))
            self._emit(Op.POP)
            raise VMError("Web framework requires interpreter mode", getattr(node, 'line', 0))
        # GUI nodes — delegate to interpreter via fallback marker
        elif hasattr(ast, 'WindowCreate') and isinstance(node, (
                ast.WindowCreate, ast.WidgetAdd, ast.LayoutBlock,
                ast.BindEvent, ast.DialogShow, ast.MenuDef, ast.CanvasDraw)):
            raise VMError("GUI requires interpreter mode", getattr(node, 'line', 0))
        # Page/HTML/Script — no-ops in VM (semantic only)
        elif isinstance(node, (ast.PageDef, ast.HtmlElement, ast.SendResponse,
                               ast.ScriptBlock, ast.StoreStatement,
                               ast.FetchStatement, ast.DeleteStatement)):
            pass  # These are web DSL nodes, no-op in VM
        elif isinstance(node, ast.FileRead):
            self._compile_expr(node)
            self._emit(Op.POP)
        else:
            # Fallback: try to compile as expression statement
            try:
                self._compile_expr(node)
                self._emit(Op.POP)
            except Exception:
                import warnings as _w
                _w.warn(f"VM: skipping unsupported statement {type(node).__name__}")

    def _compile_print(self, node):
        # PrintStatement has .expression (single expr), not .values
        if hasattr(node, 'values'):
            for val in node.values:
                self._compile_expr(val)
            self._emit(Op.PRINT, len(node.values))
        else:
            self._compile_expr(node.expression)
            self._emit(Op.PRINT, 1)

    def _compile_var_decl(self, node):
        self._compile_expr(node.value)
        idx = self._declare_local(node.name)
        self._emit(Op.STORE_VAR, idx)

    def _compile_assignment(self, node):
        self._compile_expr(node.value)
        idx = self._resolve_local(node.name)
        if idx is not None:
            self._emit(Op.STORE_VAR, idx)
        else:
            self._emit(Op.STORE_GLOBAL, node.name)

    def _compile_aug_assign(self, node):
        op_map = {'Plus': Op.ADD, 'Minus': Op.SUB,
                  'Multiply': Op.MUL, 'Divide': Op.DIV,
                  '+=': Op.ADD, '-=': Op.SUB,
                  '*=': Op.MUL, '/=': Op.DIV,
                  '%=': Op.MOD}
        idx = self._resolve_local(node.name)
        if idx is not None:
            self._emit(Op.LOAD_VAR, idx)
        else:
            self._emit(Op.LOAD_GLOBAL, node.name)
        self._compile_expr(node.value)
        op_type = getattr(node, 'op', None) or getattr(node, 'operator', 'Plus')
        vm_op = op_map.get(str(op_type), Op.ADD)
        self._emit(vm_op)
        if idx is not None:
            self._emit(Op.STORE_VAR, idx)
        else:
            self._emit(Op.STORE_GLOBAL, node.name)

    def _compile_index_assign(self, node):
        self._compile_expr(node.value)
        obj = node.object if hasattr(node, 'object') else node
        name = getattr(obj, 'name', None) or getattr(node, 'name', None)
        if name:
            idx = self._resolve_local(name)
            if idx is not None:
                self._emit(Op.LOAD_VAR, idx)
            else:
                self._emit(Op.LOAD_GLOBAL, name)
        if hasattr(node, 'index'):
            self._compile_expr(node.index)
        self._emit(Op.INDEX_STORE)

    def _compile_if(self, node):
        self._compile_expr(node.condition)
        false_jump = self._emit_jump(Op.JUMP_IF_FALSE)

        for stmt in node.then_body:
            self._compile_stmt(stmt)

        if node.else_body or (hasattr(node, 'elif_clauses') and node.elif_clauses):
            end_jump = self._emit_jump(Op.JUMP)
            self._patch_jump(false_jump)

            if hasattr(node, 'elif_clauses') and node.elif_clauses:
                end_jumps = [end_jump]
                for elif_cond, elif_body in node.elif_clauses:
                    self._compile_expr(elif_cond)
                    next_false = self._emit_jump(Op.JUMP_IF_FALSE)
                    for stmt in elif_body:
                        self._compile_stmt(stmt)
                    end_jumps.append(self._emit_jump(Op.JUMP))
                    self._patch_jump(next_false)
                if node.else_body:
                    for stmt in node.else_body:
                        self._compile_stmt(stmt)
                for ej in end_jumps:
                    self._patch_jump(ej)
            else:
                for stmt in node.else_body:
                    self._compile_stmt(stmt)
                self._patch_jump(end_jump)
        else:
            self._patch_jump(false_jump)

    def _compile_while(self, node):
        loop_start = len(self.instructions)
        self.loop_stack.append({'continue': loop_start, 'breaks': []})

        self._compile_expr(node.condition)
        exit_jump = self._emit_jump(Op.JUMP_IF_FALSE)

        for stmt in node.body:
            self._compile_stmt(stmt)

        self._emit(Op.LOOP_BACK, loop_start)
        self._patch_jump(exit_jump)

        loop_info = self.loop_stack.pop()
        for brk in loop_info['breaks']:
            self._patch_jump(brk)

    def _compile_for(self, node):
        # Compile: For <var> From <start> To <end> [Step <step>]
        start_val = node.start if hasattr(node, 'start') else node.range_start
        end_val = node.end if hasattr(node, 'end') else node.range_end
        step_val = getattr(node, 'step', None)

        # Initialize counter
        self._compile_expr(start_val)
        var_name = node.var_name if hasattr(node, 'var_name') else node.variable
        var_idx = self._declare_local(var_name)
        self._emit(Op.STORE_VAR, var_idx)

        loop_start = len(self.instructions)
        self.loop_stack.append({'continue': loop_start, 'breaks': []})

        # Check condition: var <= end
        self._emit(Op.LOAD_VAR, var_idx)
        self._compile_expr(end_val)
        self._emit(Op.LTE)
        exit_jump = self._emit_jump(Op.JUMP_IF_FALSE)

        # Body
        for stmt in node.body:
            self._compile_stmt(stmt)

        # Increment
        self._emit(Op.LOAD_VAR, var_idx)
        if step_val:
            self._compile_expr(step_val)
        else:
            self._emit(Op.LOAD_CONST, self._add_const(1))
        self._emit(Op.ADD)
        self._emit(Op.STORE_VAR, var_idx)

        self._emit(Op.LOOP_BACK, loop_start)
        self._patch_jump(exit_jump)

        loop_info = self.loop_stack.pop()
        for brk in loop_info['breaks']:
            self._patch_jump(brk)

    def _compile_foreach(self, node):
        # Compile the iterable
        self._compile_expr(node.iterable)
        self._emit(Op.GET_ITER)

        var_idx = self._declare_local(node.var_name)
        loop_start = len(self.instructions)
        self.loop_stack.append({'continue': loop_start, 'breaks': []})

        exit_jump = self._emit(Op.FOR_ITER, -1)

        self._emit(Op.STORE_VAR, var_idx)

        for stmt in node.body:
            self._compile_stmt(stmt)

        self._emit(Op.LOOP_BACK, loop_start)
        self._patch_jump(exit_jump)

        loop_info = self.loop_stack.pop()
        for brk in loop_info['breaks']:
            self._patch_jump(brk)

        self._emit(Op.POP)  # Pop iterator

    def _compile_repeat(self, node):
        # Repeat <count> Times ... EndRepeat
        self._compile_expr(node.count)
        counter_idx = self._declare_local(f"__repeat_{self._label_counter}")
        self._label_counter += 1
        self._emit(Op.STORE_VAR, counter_idx)

        # Initialize loop var to 0
        iter_idx = self._declare_local(f"__iter_{self._label_counter}")
        self._emit(Op.LOAD_CONST, self._add_const(0))
        self._emit(Op.STORE_VAR, iter_idx)

        loop_start = len(self.instructions)
        self.loop_stack.append({'continue': loop_start, 'breaks': []})

        # Check: iter < count
        self._emit(Op.LOAD_VAR, iter_idx)
        self._emit(Op.LOAD_VAR, counter_idx)
        self._emit(Op.LT)
        exit_jump = self._emit_jump(Op.JUMP_IF_FALSE)

        for stmt in node.body:
            self._compile_stmt(stmt)

        # iter += 1
        self._emit(Op.LOAD_VAR, iter_idx)
        self._emit(Op.LOAD_CONST, self._add_const(1))
        self._emit(Op.ADD)
        self._emit(Op.STORE_VAR, iter_idx)

        self._emit(Op.LOOP_BACK, loop_start)
        self._patch_jump(exit_jump)

        loop_info = self.loop_stack.pop()
        for brk in loop_info['breaks']:
            self._patch_jump(brk)

    def _compile_func_def(self, node):
        """Compile a function definition into a CompiledFunction."""
        # Save state
        outer_instructions = self.instructions
        outer_scope = self.locals_stack[-1]

        self.instructions = []
        self.locals_stack.append({})

        # Declare parameters as locals
        from epl.ast_nodes import RestParameter
        params = node.params if hasattr(node, 'params') else getattr(node, 'parameters', [])
        param_names = []
        defaults = []
        rest_param_name = None
        for p in params:
            if isinstance(p, RestParameter):
                rest_param_name = p.name
                param_names.append(p.name)
                defaults.append(None)
            elif isinstance(p, tuple):
                # 3-tuple: (name, type, default) or 2-tuple: (name, default)
                name = p[0]
                default = p[-1] if len(p) == 2 else p[2] if len(p) >= 3 else None
                param_names.append(name)
                defaults.append(default)
            elif isinstance(p, str):
                param_names.append(p)
                defaults.append(None)
            else:
                pname = getattr(p, 'name', str(p))
                param_names.append(pname)
                defaults.append(getattr(p, 'default', None))
            self._declare_local(param_names[-1])

        # Compile body
        body = node.body if isinstance(node.body, list) else [node.body]
        for stmt in body:
            self._compile_stmt(stmt)

        # Ensure return
        if not self.instructions or self.instructions[-1].op != Op.RETURN:
            self._emit(Op.LOAD_CONST, self._add_const(None))
            self._emit(Op.RETURN)

        func = CompiledFunction(
            name=node.name,
            param_count=len(param_names),
            param_names=param_names,
            defaults=defaults,
            code=self.instructions,
            local_count=len(self.locals_stack[-1]),
        )
        func.rest_param_name = rest_param_name

        # Restore state
        self.instructions = outer_instructions
        self.locals_stack.pop()

        self.functions[node.name] = func
        # Also store reference in current scope
        idx = self._declare_local(node.name)
        self._emit(Op.LOAD_CONST, self._add_const(func))
        self._emit(Op.STORE_VAR, idx)

    def _compile_async_func_def(self, node):
        """Compile async function — stores with is_async flag for VM runtime."""
        # Save state
        outer_instructions = self.instructions
        outer_scope = self.locals_stack[-1]

        self.instructions = []
        self.locals_stack.append({})

        params = node.params if hasattr(node, 'params') else getattr(node, 'parameters', [])
        param_names = []
        defaults = []
        for p in params:
            if isinstance(p, tuple):
                name = p[0]
                default = p[-1] if len(p) == 2 else p[2] if len(p) >= 3 else None
                param_names.append(name)
                defaults.append(default)
            elif isinstance(p, str):
                param_names.append(p)
                defaults.append(None)
            else:
                pname = getattr(p, 'name', str(p))
                param_names.append(pname)
                defaults.append(getattr(p, 'default', None))
            self._declare_local(param_names[-1])

        body = node.body if isinstance(node.body, list) else [node.body]
        for stmt in body:
            self._compile_stmt(stmt)

        if not self.instructions or self.instructions[-1].op != Op.RETURN:
            self._emit(Op.LOAD_CONST, self._add_const(None))
            self._emit(Op.RETURN)

        func = CompiledFunction(
            name=node.name,
            param_count=len(param_names),
            param_names=param_names,
            defaults=defaults,
            code=self.instructions,
            local_count=len(self.locals_stack[-1]),
        )
        func.is_async = True  # Mark as async

        self.instructions = outer_instructions
        self.locals_stack.pop()

        self.functions[node.name] = func
        idx = self._declare_local(node.name)
        self._emit(Op.LOAD_CONST, self._add_const(func))
        self._emit(Op.STORE_VAR, idx)

    def _compile_class_def(self, node):
        """Compile a class definition."""
        methods = {}
        properties = {}
        constructor = None

        for member in (node.body if isinstance(node.body, list) else []):
            from epl import ast_nodes as ast
            if isinstance(member, ast.FunctionDef):
                # Save state
                outer_instr = self.instructions
                self.instructions = []
                self.locals_stack.append({})
                self._declare_local('this')  # 'this' is always local 0 in methods

                params = member.params if hasattr(member, 'params') else getattr(member, 'parameters', [])
                param_names = ['this']
                defaults = [None]
                for p in params:
                    if isinstance(p, tuple):
                        name = p[0]
                        default = p[-1] if len(p) == 2 else p[2] if len(p) >= 3 else None
                    elif isinstance(p, str):
                        name, default = p, None
                    else:
                        name = getattr(p, 'name', str(p))
                        default = getattr(p, 'default', None)
                    param_names.append(name)
                    defaults.append(default)
                    self._declare_local(name)

                body = member.body if isinstance(member.body, list) else [member.body]
                for stmt in body:
                    self._compile_stmt(stmt)

                if not self.instructions or self.instructions[-1].op != Op.RETURN:
                    self._emit(Op.LOAD_CONST, self._add_const(None))
                    self._emit(Op.RETURN)

                mfunc = CompiledFunction(
                    name=member.name,
                    param_count=len(param_names),
                    param_names=param_names,
                    defaults=defaults,
                    code=self.instructions,
                    local_count=len(self.locals_stack[-1]),
                    is_method=True,
                )

                self.instructions = outer_instr
                self.locals_stack.pop()

                if member.name in ('Constructor', 'Init', '__init__'):
                    constructor = mfunc
                methods[member.name] = mfunc

            elif isinstance(member, ast.VarDeclaration):
                properties[member.name] = None

        compiled = CompiledClass(
            name=node.name,
            methods=methods,
            properties=properties,
            parent=getattr(node, 'parent', None),
            constructor=constructor,
        )
        self.classes[node.name] = compiled
        idx = self._declare_local(node.name)
        self._emit(Op.LOAD_CONST, self._add_const(compiled))
        self._emit(Op.STORE_VAR, idx)

    def _compile_try_catch(self, node):
        handler_jump = self._emit(Op.SETUP_TRY, -1)

        for stmt in node.try_body:
            self._compile_stmt(stmt)

        self._emit(Op.POP_TRY)
        end_jump = self._emit_jump(Op.JUMP)

        self._patch_jump(handler_jump)
        # Store exception in catch variable
        if hasattr(node, 'catch_var') and node.catch_var:
            idx = self._declare_local(node.catch_var)
            self._emit(Op.STORE_VAR, idx)
        else:
            self._emit(Op.POP)

        catch_body = node.catch_body if hasattr(node, 'catch_body') else []
        for stmt in catch_body:
            self._compile_stmt(stmt)

        self._patch_jump(end_jump)

        if hasattr(node, 'finally_body') and node.finally_body:
            for stmt in node.finally_body:
                self._compile_stmt(stmt)

    def _compile_match(self, node):
        self._compile_expr(node.value)
        end_jumps = []

        for case in node.cases:
            self._emit(Op.DUP)
            if hasattr(case, 'pattern'):
                self._compile_expr(case.pattern)
            elif isinstance(case, tuple):
                self._compile_expr(case[0])
            self._emit(Op.EQ)
            next_case = self._emit_jump(Op.JUMP_IF_FALSE)

            self._emit(Op.POP)  # Pop matched value
            body = case.body if hasattr(case, 'body') else case[1]
            for stmt in (body if isinstance(body, list) else [body]):
                self._compile_stmt(stmt)
            end_jumps.append(self._emit_jump(Op.JUMP))

            self._patch_jump(next_case)

        self._emit(Op.POP)  # Pop unmatched value
        # Default case
        if hasattr(node, 'default') and node.default:
            for stmt in node.default:
                self._compile_stmt(stmt)

        for ej in end_jumps:
            self._patch_jump(ej)

    def _compile_enum(self, node):
        """Compile enum as a dict constant."""
        members = {}
        for i, name in enumerate(node.members if hasattr(node, 'members') else node.values):
            if isinstance(name, tuple):
                members[name[0]] = name[1]
            else:
                members[name] = i
        idx = self._declare_local(node.name)
        self._emit(Op.LOAD_CONST, self._add_const(members))
        self._emit(Op.STORE_VAR, idx)

    # ─── Expression compilation ───────────────────────────────

    def _compile_expr(self, node):
        from epl import ast_nodes as ast

        if node is None:
            self._emit(Op.LOAD_CONST, self._add_const(None))
            return

        self._current_line = getattr(node, 'line', self._current_line)

        if isinstance(node, ast.Literal) and isinstance(node.value, (int, float)):
            self._emit(Op.LOAD_CONST, self._add_const(node.value))

        elif isinstance(node, ast.Literal) and isinstance(node.value, str):
            val = node.value
            # Handle interpolation: look for {expr} in string
            if '{' in val and '}' in val:
                self._compile_interpolated_string(val)
            else:
                self._emit(Op.LOAD_CONST, self._add_const(val))

        elif isinstance(node, ast.Literal) and isinstance(node.value, bool):
            self._emit(Op.LOAD_CONST, self._add_const(node.value))

        elif isinstance(node, ast.Literal) and node.value is None:
            self._emit(Op.LOAD_CONST, self._add_const(None))

        elif isinstance(node, ast.Identifier):
            name = node.name if hasattr(node, 'name') else node.value
            idx = self._resolve_local(name)
            if idx is not None:
                self._emit(Op.LOAD_VAR, idx)
            else:
                self._emit(Op.LOAD_GLOBAL, name)

        elif isinstance(node, ast.BinaryOp):
            self._compile_binary(node)

        elif isinstance(node, ast.UnaryOp):
            self._compile_expr(node.operand)
            if node.operator in ('Minus', 'MINUS', '-'):
                self._emit(Op.NEG)
            elif node.operator in ('Not', 'NOT', '!', 'not'):
                self._emit(Op.NOT)

        elif isinstance(node, ast.FunctionCall):
            self._compile_call(node)

        elif isinstance(node, ast.MethodCall):
            self._compile_method_call(node)

        elif isinstance(node, ast.ListLiteral):
            for elem in node.elements:
                self._compile_expr(elem)
            self._emit(Op.BUILD_LIST, len(node.elements))

        elif isinstance(node, ast.DictLiteral):
            for key, val in node.pairs:
                self._compile_expr(key)
                self._compile_expr(val)
            self._emit(Op.BUILD_DICT, len(node.pairs))

        elif isinstance(node, ast.IndexAccess):
            self._compile_expr(node.object)
            self._compile_expr(node.index)
            self._emit(Op.INDEX)

        elif isinstance(node, ast.PropertyAccess):
            self._compile_expr(node.obj)
            self._emit(Op.GET_ATTR, node.property_name)

        elif isinstance(node, ast.TernaryExpression):
            self._compile_expr(node.condition)
            false_jump = self._emit_jump(Op.JUMP_IF_FALSE)
            self._compile_expr(node.true_value)
            end_jump = self._emit_jump(Op.JUMP)
            self._patch_jump(false_jump)
            self._compile_expr(node.false_value)
            self._patch_jump(end_jump)

        elif isinstance(node, ast.LambdaExpression):
            self._compile_lambda(node)

        elif isinstance(node, ast.SliceAccess):
            self._compile_expr(node.object)
            self._compile_expr(node.start) if node.start else self._emit(Op.LOAD_CONST, self._add_const(None))
            self._compile_expr(node.end) if node.end else self._emit(Op.LOAD_CONST, self._add_const(None))
            self._emit(Op.SLICE)

        elif hasattr(ast, 'TypeCast') and isinstance(node, ast.TypeCast):
            self._compile_expr(node.value)
            self._emit(Op.CALL_BUILTIN, ('type_cast', node.target_type))

        elif isinstance(node, (int, float)):
            self._emit(Op.LOAD_CONST, self._add_const(node))

        elif isinstance(node, str):
            self._emit(Op.LOAD_CONST, self._add_const(node))

        elif isinstance(node, bool):
            self._emit(Op.LOAD_CONST, self._add_const(node))

        # Phase 6: Full expression parity
        elif isinstance(node, ast.NewInstance):
            for a in node.arguments:
                self._compile_expr(a)
            self._emit(Op.NEW_INSTANCE, (node.class_name, len(node.arguments)))

        elif isinstance(node, ast.FileRead):
            self._compile_expr(node.path)
            self._emit(Op.FILE_READ)

        elif hasattr(ast, 'AwaitExpression') and isinstance(node, ast.AwaitExpression):
            self._compile_expr(node.expression)
            self._emit(Op.AWAIT)

        elif hasattr(ast, 'SuperCall') and isinstance(node, ast.SuperCall):
            for a in node.arguments:
                self._compile_expr(a)
            self._emit(Op.SUPER_CALL, (node.method_name, len(node.arguments)))

        elif hasattr(ast, 'ModuleAccess') and isinstance(node, ast.ModuleAccess):
            self._emit(Op.LOAD_GLOBAL, node.module_name)
            self._emit(Op.GET_ATTR, node.member_name)

        else:
            # Unknown expression type - push None
            self._emit(Op.LOAD_CONST, self._add_const(None))

    def _compile_interpolated_string(self, template):
        """Compile a string with {expr} interpolation."""
        import re
        parts = re.split(r'\{([^}]+)\}', template)
        count = 0
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Static string part
                if part:
                    self._emit(Op.LOAD_CONST, self._add_const(part))
                    count += 1
            else:
                # Expression part - compile as variable lookup
                self._emit(Op.LOAD_GLOBAL, part.strip())
                self._emit(Op.CALL_BUILTIN, ('to_string', 1))
                count += 1
        if count == 0:
            self._emit(Op.LOAD_CONST, self._add_const(""))
        elif count == 1:
            pass  # Already on stack
        else:
            self._emit(Op.STR_INTERP, count)

    def _compile_binary(self, node):
        from epl import ast_nodes as ast_mod
        op_map = {
            'Plus': Op.ADD, 'Minus': Op.SUB,
            'Multiply': Op.MUL, 'Divide': Op.DIV,
            'Modulo': Op.MOD, 'Power': Op.POW,
            'FloorDivide': Op.FLOOR_DIV,
            'PLUS': Op.ADD, 'MINUS': Op.SUB,
            'MULTIPLY': Op.MUL, 'DIVIDE': Op.DIV,
            'MODULO': Op.MOD, 'POWER': Op.POW,
            '+': Op.ADD, '-': Op.SUB,
            '*': Op.MUL, '/': Op.DIV,
            '%': Op.MOD, '**': Op.POW, '//': Op.FLOOR_DIV,
            # Comparison
            'Equals': Op.EQ, 'NotEquals': Op.NEQ,
            'LessThan': Op.LT, 'GreaterThan': Op.GT,
            'LessThanOrEqual': Op.LTE, 'GreaterThanOrEqual': Op.GTE,
            'EQUALS': Op.EQ, 'NOT_EQUALS': Op.NEQ,
            'LESS_THAN': Op.LT, 'GREATER_THAN': Op.GT,
            '==': Op.EQ, '!=': Op.NEQ,
            '<': Op.LT, '>': Op.GT,
            '<=': Op.LTE, '>=': Op.GTE,
            'Is': Op.EQ, 'IsNot': Op.NEQ,
            # Logical
            'And': Op.AND, 'Or': Op.OR,
            'AND': Op.AND, 'OR': Op.OR,
            'and': Op.AND, 'or': Op.OR,
            '&&': Op.AND, '||': Op.OR,
        }

        # Constant folding: if both sides are literals, compute at compile time
        if isinstance(node.left, ast_mod.Literal) and isinstance(node.right, ast_mod.Literal):
            lv, rv = node.left.value, node.right.value
            op_str = str(node.operator)
            if isinstance(lv, (int, float)) and isinstance(rv, (int, float)):
                try:
                    fold_ops = {
                        '+': operator.add, 'Plus': operator.add, 'PLUS': operator.add,
                        '-': operator.sub, 'Minus': operator.sub, 'MINUS': operator.sub,
                        '*': operator.mul, 'Multiply': operator.mul, 'MULTIPLY': operator.mul,
                        '/': operator.truediv, 'Divide': operator.truediv, 'DIVIDE': operator.truediv,
                        '%': operator.mod, 'Modulo': operator.mod, 'MODULO': operator.mod,
                        '**': operator.pow, 'Power': operator.pow, 'POWER': operator.pow,
                        '//': operator.floordiv, 'FloorDivide': operator.floordiv,
                    }
                    if op_str in fold_ops and (op_str not in ('/', 'Divide', 'DIVIDE') or rv != 0):
                        result = fold_ops[op_str](lv, rv)
                        idx = self._add_const(result)
                        self._emit(Op.LOAD_CONST, idx)
                        return
                    # Comparison constant folding
                    cmp_fold = {
                        '==': operator.eq, 'Equals': operator.eq, 'EQUALS': operator.eq, 'Is': operator.eq,
                        '!=': operator.ne, 'NotEquals': operator.ne, 'NOT_EQUALS': operator.ne, 'IsNot': operator.ne,
                        '<': operator.lt, 'LessThan': operator.lt, 'LESS_THAN': operator.lt,
                        '>': operator.gt, 'GreaterThan': operator.gt, 'GREATER_THAN': operator.gt,
                        '<=': operator.le, 'LessThanOrEqual': operator.le,
                        '>=': operator.ge, 'GreaterThanOrEqual': operator.ge,
                    }
                    if op_str in cmp_fold:
                        result = cmp_fold[op_str](lv, rv)
                        self._emit(Op.LOAD_CONST, self._add_const(result))
                        return
                except (ZeroDivisionError, OverflowError, ValueError):
                    pass
            elif isinstance(lv, str) and isinstance(rv, str) and op_str in ('+', 'Plus', 'PLUS'):
                idx = self._add_const(lv + rv)
                self._emit(Op.LOAD_CONST, idx)
                return

        self._compile_expr(node.left)
        self._compile_expr(node.right)
        op_str = str(node.operator)
        if op_str in op_map:
            self._emit(op_map[op_str])
        else:
            self._emit(Op.ADD)

    def _compile_comparison(self, node):
        cmp_map = {
            'Equals': Op.EQ, 'NotEquals': Op.NEQ,
            'LessThan': Op.LT, 'GreaterThan': Op.GT,
            'LessThanOrEqual': Op.LTE, 'GreaterThanOrEqual': Op.GTE,
            'EQUALS': Op.EQ, 'NOT_EQUALS': Op.NEQ,
            'LESS_THAN': Op.LT, 'GREATER_THAN': Op.GT,
            '==': Op.EQ, '!=': Op.NEQ,
            '<': Op.LT, '>': Op.GT,
            '<=': Op.LTE, '>=': Op.GTE,
            'Is': Op.EQ, 'IsNot': Op.NEQ,
        }
        self._compile_expr(node.left)
        self._compile_expr(node.right)
        op_str = str(node.operator)
        self._emit(cmp_map.get(op_str, Op.EQ))

    def _compile_logical(self, node):
        self._compile_expr(node.left)
        if str(node.operator) in ('And', 'AND', 'and', '&&'):
            jump = self._emit_jump(Op.JUMP_IF_FALSE)
            self._emit(Op.POP)
            self._compile_expr(node.right)
            self._patch_jump(jump)
        else:  # Or
            jump = self._emit_jump(Op.JUMP_IF_TRUE)
            self._emit(Op.POP)
            self._compile_expr(node.right)
            self._patch_jump(jump)

    def _compile_call(self, node):
        name = node.name if isinstance(node.name, str) else getattr(node.name, 'name', str(node.name))
        args = node.args if hasattr(node, 'args') else getattr(node, 'arguments', [])

        for arg in args:
            self._compile_expr(arg)

        # Check if it's a known function
        if name in self.functions:
            self._emit(Op.CALL, (name, len(args)))
        else:
            # Could be a builtin or class constructor
            self._emit(Op.CALL_BUILTIN, (name, len(args)))

    def _compile_method_call(self, node):
        self._compile_expr(node.obj)
        args = node.arguments if hasattr(node, 'arguments') else getattr(node, 'args', [])
        for arg in args:
            self._compile_expr(arg)
        method = node.method_name if isinstance(node.method_name, str) else getattr(node.method_name, 'name', str(node.method_name))
        self._emit(Op.CALL_METHOD, (method, len(args)))

    def _compile_lambda(self, node):
        outer_instr = self.instructions
        self.instructions = []
        self.locals_stack.append({})

        params = node.params if hasattr(node, 'params') else getattr(node, 'parameters', [])
        param_names = []
        for p in params:
            name = p if isinstance(p, str) else getattr(p, 'name', str(p))
            param_names.append(name)
            self._declare_local(name)

        if isinstance(node.body, list):
            for stmt in node.body:
                self._compile_stmt(stmt)
        else:
            self._compile_expr(node.body)
            self._emit(Op.RETURN)

        if not self.instructions or self.instructions[-1].op != Op.RETURN:
            self._emit(Op.LOAD_CONST, self._add_const(None))
            self._emit(Op.RETURN)

        lname = f"__lambda_{self._label_counter}"
        self._label_counter += 1

        func = CompiledFunction(
            name=lname,
            param_count=len(param_names),
            param_names=param_names,
            defaults=[],
            code=self.instructions,
            local_count=len(self.locals_stack[-1]),
        )

        self.instructions = outer_instr
        self.locals_stack.pop()

        self.functions[lname] = func
        self._emit(Op.LOAD_CONST, self._add_const(func))

    def disassemble(self, code=None):
        """Return human-readable disassembly."""
        code = code or self.instructions
        lines = []
        for i, inst in enumerate(code):
            lines.append(f"{i:4d}  {inst}")
        return '\n'.join(lines)


# ─── Virtual Machine ─────────────────────────────────────────

class VMInstance:
    """Represents a class instance in the VM."""
    __slots__ = ('class_def', 'attrs')

    def __init__(self, class_def):
        self.class_def = class_def
        self.attrs = dict(class_def.properties)


class VMIterator:
    """Iterator wrapper for the VM."""
    __slots__ = ('items', 'index')

    def __init__(self, items):
        self.items = list(items) if not isinstance(items, list) else items
        self.index = 0

    def has_next(self):
        return self.index < len(self.items)

    def next(self):
        val = self.items[self.index]
        self.index += 1
        return val


class VMClosure:
    """Represents a closure capturing free variables."""
    __slots__ = ('func', 'cells')

    def __init__(self, func, cells):
        self.func = func
        self.cells = cells


class VM:
    """
    Stack-based virtual machine for executing EPL bytecode.

    Performance improvements over tree-walking:
    - No AST node allocation during execution
    - Direct instruction dispatch (switch/dict) instead of isinstance chains
    - Local variables indexed by slot number instead of dict lookup
    - Constant pool for literal deduplication
    - Tight execution loop with minimal Python overhead
    """

    MAX_CALL_DEPTH = 500  # Maximum call stack depth

    def __init__(self):
        self.stack: list = []
        self.call_stack: list = []
        self.globals: dict = {}
        self.output_lines: list = []
        self.functions: dict = {}
        self.classes: dict = {}
        self.constants: list = []
        self.try_stack: list = []   # Exception handler addresses
        self.const_names: set = set()  # Track constant variable names
        self._builtins = self._init_builtins()
        self._builtin_dispatch = self._build_builtin_dispatch()
        self._dispatch = self._build_dispatch_table()
        self._imported_modules = set()  # Track imported files for dedup
        # Performance counters
        self.instruction_count = 0
        self.start_time = 0.0

    def _build_dispatch_table(self):
        """Build opcode → handler dispatch table for fast execution."""
        # Use list indexed by opcode value for O(1) lookup (faster than dict hash)
        max_op = max(op.value for op in Op)
        table = [None] * (max_op + 1)
        handlers = {
            Op.LOAD_CONST: self._op_load_const,
            Op.LOAD_VAR: self._op_load_var,
            Op.STORE_VAR: self._op_store_var,
            Op.LOAD_GLOBAL: self._op_load_global,
            Op.STORE_GLOBAL: self._op_store_global,
            Op.POP: self._op_pop,
            Op.DUP: self._op_dup,
            Op.ROT_TWO: self._op_rot_two,
            Op.ADD: self._op_add,
            Op.SUB: self._op_sub,
            Op.MUL: self._op_mul,
            Op.DIV: self._op_div,
            Op.MOD: self._op_mod,
            Op.POW: self._op_pow,
            Op.FLOOR_DIV: self._op_floor_div,
            Op.NEG: self._op_neg,
            Op.EQ: self._op_eq,
            Op.NEQ: self._op_neq,
            Op.LT: self._op_lt,
            Op.GT: self._op_gt,
            Op.LTE: self._op_lte,
            Op.GTE: self._op_gte,
            Op.AND: self._op_and,
            Op.OR: self._op_or,
            Op.NOT: self._op_not,
            Op.CONCAT: self._op_concat,
            Op.STR_INTERP: self._op_str_interp,
            Op.JUMP: self._op_jump,
            Op.JUMP_IF_FALSE: self._op_jump_if_false,
            Op.JUMP_IF_TRUE: self._op_jump_if_true,
            Op.LOOP_BACK: self._op_loop_back,
            Op.CALL: self._op_call,
            Op.RETURN: self._op_return,
            Op.CALL_BUILTIN: self._op_call_builtin,
            Op.BUILD_LIST: self._op_build_list,
            Op.BUILD_DICT: self._op_build_dict,
            Op.INDEX: self._op_index,
            Op.INDEX_STORE: self._op_index_store,
            Op.SLICE: self._op_slice,
            Op.GET_ATTR: self._op_get_attr,
            Op.SET_ATTR: self._op_set_attr,
            Op.CALL_METHOD: self._op_call_method,
            Op.PRINT: self._op_print,
            Op.INPUT: self._op_input,
            Op.GET_ITER: self._op_get_iter,
            Op.FOR_ITER: self._op_for_iter,
            Op.RANGE: self._op_range,
            Op.IMPORT: self._op_import,
            Op.HALT: self._op_halt,
            Op.SETUP_TRY: self._op_setup_try,
            Op.POP_TRY: self._op_pop_try,
            Op.THROW: self._op_throw,
            Op.NEW_INSTANCE: self._op_new_instance,
            Op.NOP: lambda i: None,
            # Previously missing opcodes
            Op.BUILD_CLASS: self._op_build_class,
            Op.MAKE_CLOSURE: self._op_make_closure,
            Op.LOAD_FREE: self._op_load_free,
            Op.STORE_FREE: self._op_store_free,
            Op.ADD_ASSIGN: self._op_add_assign,
            Op.SUB_ASSIGN: self._op_sub_assign,
            Op.MUL_ASSIGN: self._op_mul_assign,
            Op.DIV_ASSIGN: self._op_div_assign,
            Op.UNPACK_SEQ: self._op_unpack_seq,
            # Phase 6: Full feature parity opcodes
            Op.YIELD: self._op_yield,
            Op.AWAIT: self._op_await,
            Op.CALL_STDLIB: self._op_call_stdlib,
            Op.IMPORT_MODULE: self._op_import_module,
            Op.FILE_READ: self._op_file_read,
            Op.SUPER_CALL: self._op_super_call,
            Op.MODULE_ACCESS: self._op_module_access,
        }
        for op, handler in handlers.items():
            table[op.value] = handler
        return table

    def execute(self, compiled):
        """Execute compiled bytecode."""
        self.constants = compiled['constants']
        self.functions.update(compiled['functions'])
        self.classes.update(compiled['classes'])
        self.start_time = time.perf_counter()

        # Create main frame
        main_func = CompiledFunction(
            name='__main__',
            param_count=0,
            param_names=[],
            defaults=[],
            code=compiled['code'],
            local_count=256,
        )
        frame = CallFrame(
            func=main_func,
            ip=0,
            base_pointer=0,
            locals=[None] * 256,
            cells=[],
        )
        self.call_stack.append(frame)

        # Main execution loop
        self._run()

        elapsed = time.perf_counter() - self.start_time
        return {
            'output': self.output_lines,
            'instructions_executed': self.instruction_count,
            'elapsed_seconds': elapsed,
            'ips': self.instruction_count / elapsed if elapsed > 0 else 0,
        }

    def _capture_call_stack(self):
        """Capture the current VM call stack as outer-to-inner frames."""
        frames = []
        for frame in self.call_stack:
            func_name = getattr(frame.func, 'name', '<anonymous>')
            if func_name == '__main__':
                func_name = 'main'
            line = 0
            code = getattr(frame.func, 'code', None) or []
            if code:
                inst_index = min(max(frame.ip - 1, 0), len(code) - 1)
                line = getattr(code[inst_index], 'line', 0) or 0
            frames.append((func_name, line))
        return frames

    def _run(self):
        """Core execution loop — optimized hot path."""
        stack = self.stack
        call_stack = self.call_stack
        dispatch = self._dispatch
        instruction_count = 0

        frame = call_stack[-1]
        code = frame.func.code
        code_len = len(code)

        while True:
            if frame.ip >= code_len:
                if len(call_stack) > 1:
                    call_stack.pop()
                    stack.append(None)
                    frame = call_stack[-1]
                    code = frame.func.code
                    code_len = len(code)
                    continue
                else:
                    break

            inst = code[frame.ip]
            frame.ip += 1
            instruction_count += 1

            handler = dispatch[inst.op]
            if handler is not None:
                try:
                    result = handler(inst)
                    if result == '__HALT__':
                        self.instruction_count += instruction_count
                        return
                    # After CALL/RETURN, frame may have changed
                    if inst.op in (Op.CALL, Op.RETURN, Op.CALL_METHOD, Op.CALL_BUILTIN):
                        if call_stack:
                            frame = call_stack[-1]
                            code = frame.func.code
                            code_len = len(code)
                        else:
                            break
                except VMError as e:
                    e.with_call_stack(self._capture_call_stack())
                    raise
                except Exception as e:
                    if self.try_stack:
                        handler_ip = self.try_stack.pop()
                        frame.ip = handler_ip
                        stack.append(str(e))
                    else:
                        raise VMError(str(e), inst.line, call_stack=self._capture_call_stack())

    # ─── Opcode handlers ─────────────────────────────────────

    def _op_load_const(self, inst):
        self.stack.append(self.constants[inst.arg])

    def _op_load_var(self, inst):
        frame = self.call_stack[-1]
        self.stack.append(frame.locals[inst.arg])

    def _op_store_var(self, inst):
        frame = self.call_stack[-1]
        frame.locals[inst.arg] = self.stack.pop()

    def _op_load_global(self, inst):
        name = inst.arg
        if name in self.globals:
            self.stack.append(self.globals[name])
        elif name in self.functions:
            self.stack.append(self.functions[name])
        elif name in self.classes:
            self.stack.append(self.classes[name])
        elif name in self._builtins:
            self.stack.append(self._builtins[name])
        else:
            self.stack.append(None)

    def _op_store_global(self, inst):
        self.globals[inst.arg] = self.stack.pop()

    def _op_pop(self, inst):
        if self.stack:
            self.stack.pop()

    def _op_dup(self, inst):
        self.stack.append(self.stack[-1])

    def _op_rot_two(self, inst):
        self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]

    # Arithmetic
    def _op_add(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        if isinstance(a, str) or isinstance(b, str):
            self.stack.append(str(a) + str(b))
        else:
            self.stack.append(a + b)

    def _op_sub(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a - b)

    def _op_mul(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a * b)

    def _op_div(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        if b == 0:
            raise VMError("Division by zero", inst.line)
        result = a / b
        self.stack.append(int(result) if result == int(result) else result)

    def _op_mod(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a % b)

    def _op_pow(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a ** b)

    def _op_floor_div(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a // b)

    def _op_neg(self, inst):
        self.stack.append(-self.stack.pop())

    # Comparison
    def _op_eq(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a == b)

    def _op_neq(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a != b)

    def _op_lt(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a < b)

    def _op_gt(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a > b)

    def _op_lte(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a <= b)

    def _op_gte(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a >= b)

    # Logical
    def _op_and(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a and b)

    def _op_or(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(a or b)

    def _op_not(self, inst):
        self.stack.append(not self.stack.pop())

    # String
    def _op_concat(self, inst):
        b, a = self.stack.pop(), self.stack.pop()
        self.stack.append(str(a) + str(b))

    def _op_str_interp(self, inst):
        count = inst.arg
        parts = []
        for _ in range(count):
            parts.append(self.stack.pop())
        parts.reverse()
        self.stack.append(''.join(str(p) for p in parts))

    # Control flow
    def _op_jump(self, inst):
        self.call_stack[-1].ip = inst.arg

    def _op_jump_if_false(self, inst):
        val = self.stack[-1]
        if not val:
            self.stack.pop()
            self.call_stack[-1].ip = inst.arg

    def _op_jump_if_true(self, inst):
        val = self.stack[-1]
        if val:
            self.call_stack[-1].ip = inst.arg

    def _op_loop_back(self, inst):
        self.call_stack[-1].ip = inst.arg

    # Functions
    def _op_call(self, inst):
        name, arg_count = inst.arg
        func = self.functions.get(name)
        if not func:
            # Try globals
            func = self.globals.get(name)
            if isinstance(func, CompiledFunction):
                pass
            elif isinstance(func, CompiledClass):
                # Constructor call
                self._call_constructor(func, arg_count)
                return
            else:
                raise VMError(f"Undefined function: {name}", inst.line)

        self._call_function(func, arg_count)

    def _call_function(self, func, arg_count):
        """Set up call frame and execute function."""
        if len(self.call_stack) >= self.MAX_CALL_DEPTH:
            raise VMError(f"Maximum recursion depth ({self.MAX_CALL_DEPTH}) exceeded in '{func.name}'.", 0)

        locals_list = [None] * max(func.local_count + 16, arg_count + 16)

        # Pop args from stack in reverse
        args = []
        for _ in range(arg_count):
            args.append(self.stack.pop())
        args.reverse()

        # Check for rest parameter
        rest_param_name = getattr(func, 'rest_param_name', None)
        if rest_param_name:
            # Rest param is the last param; regular params are all but last
            regular_count = func.param_count - 1
            for i in range(min(regular_count, len(args))):
                locals_list[i] = args[i]
            # Fill defaults for missing regular params
            for i in range(len(args), regular_count):
                if i < len(func.defaults) and func.defaults[i] is not None:
                    locals_list[i] = func.defaults[i]
            # Collect remaining args into rest param list
            rest_values = list(args[regular_count:]) if len(args) > regular_count else []
            locals_list[regular_count] = rest_values
        else:
            # Fill params
            for i, val in enumerate(args):
                if i < len(locals_list):
                    locals_list[i] = val

            # Fill defaults for missing params
            for i in range(arg_count, func.param_count):
                if i < len(func.defaults) and func.defaults[i] is not None:
                    locals_list[i] = func.defaults[i]

        frame = CallFrame(
            func=func,
            ip=0,
            base_pointer=len(self.stack),
            locals=locals_list,
            cells=[],
        )
        self.call_stack.append(frame)

    def _call_constructor(self, cls, arg_count):
        """Create new instance and call constructor."""
        instance = VMInstance(cls)

        # Set default properties
        for prop, default in cls.properties.items():
            instance.attrs[prop] = default

        if cls.constructor:
            # Push instance as first arg (this)
            args = []
            for _ in range(arg_count):
                args.append(self.stack.pop())
            args.reverse()

            self.stack.append(instance)
            for a in args:
                self.stack.append(a)

            self._call_function(cls.constructor, arg_count + 1)
            # After constructor returns, push instance
            # The return value is discarded; instance is the result
            return

        # No constructor: pop args, push instance
        for _ in range(arg_count):
            self.stack.pop()
        self.stack.append(instance)

    def _op_return(self, inst):
        ret_val = self.stack.pop() if self.stack else None
        self.call_stack.pop()
        self.stack.append(ret_val)

    def _op_call_builtin(self, inst):
        if isinstance(inst.arg, tuple):
            name, arg_count = inst.arg
        else:
            name, arg_count = inst.arg, 0

        # Special builtins
        if name == 'to_string':
            val = self.stack.pop()
            self.stack.append(str(val) if val is not None else "")
            return

        if name == 'type_cast':
            val = self.stack.pop()
            target = arg_count  # In this case, arg_count is the target type
            self.stack.append(self._type_cast(val, target))
            return

        # Check if it's actually a compiled function
        func = self.functions.get(name)
        if func:
            self._call_function(func, arg_count)
            return

        # Check if it's a class constructor
        cls = self.classes.get(name)
        if cls:
            self._call_constructor(cls, arg_count)
            return

        # Pop args
        args = []
        for _ in range(arg_count):
            args.append(self.stack.pop())
        args.reverse()

        result = self._exec_builtin(name, args, inst.line)
        self.stack.append(result)

    # Data structures
    def _op_build_list(self, inst):
        count = inst.arg
        items = []
        for _ in range(count):
            items.append(self.stack.pop())
        items.reverse()
        self.stack.append(items)

    def _op_build_dict(self, inst):
        count = inst.arg
        d = {}
        pairs = []
        for _ in range(count * 2):
            pairs.append(self.stack.pop())
        pairs.reverse()
        for i in range(0, len(pairs), 2):
            d[pairs[i]] = pairs[i + 1]
        self.stack.append(d)

    def _op_index(self, inst):
        idx = self.stack.pop()
        obj = self.stack.pop()
        if isinstance(obj, list):
            self.stack.append(obj[int(idx)])
        elif isinstance(obj, dict):
            self.stack.append(obj.get(idx))
        elif isinstance(obj, str):
            self.stack.append(obj[int(idx)])
        else:
            self.stack.append(None)

    def _op_index_store(self, inst):
        idx = self.stack.pop()
        obj = self.stack.pop()
        val = self.stack.pop()
        if isinstance(obj, list):
            obj[int(idx)] = val
        elif isinstance(obj, dict):
            obj[idx] = val

    def _op_slice(self, inst):
        end = self.stack.pop()
        start = self.stack.pop()
        obj = self.stack.pop()
        s = int(start) if start is not None else None
        e = int(end) if end is not None else None
        self.stack.append(obj[s:e])

    # Object/Class
    def _op_get_attr(self, inst):
        obj = self.stack.pop()
        attr = inst.arg
        if isinstance(obj, VMInstance):
            if attr in obj.attrs:
                self.stack.append(obj.attrs[attr])
            else:
                self.stack.append(None)
        elif isinstance(obj, dict):
            self.stack.append(obj.get(attr))
        else:
            self.stack.append(getattr(obj, attr, None))

    def _op_set_attr(self, inst):
        val = self.stack.pop()
        obj = self.stack.pop()
        attr = inst.arg
        if isinstance(obj, VMInstance):
            obj.attrs[attr] = val
        elif isinstance(obj, dict):
            obj[attr] = val

    def _op_call_method(self, inst):
        method_name, arg_count = inst.arg
        # Pop args
        args = []
        for _ in range(arg_count):
            args.append(self.stack.pop())
        args.reverse()
        # Pop object
        obj = self.stack.pop()

        if isinstance(obj, VMInstance):
            cls = obj.class_def
            # Look up method in class hierarchy
            method = cls.methods.get(method_name)
            if method:
                # Push instance as 'this'
                self.stack.append(obj)
                for a in args:
                    self.stack.append(a)
                self._call_function(method, arg_count + 1)
                return

            # Check parent class
            if cls.parent and cls.parent in self.classes:
                parent = self.classes[cls.parent]
                method = parent.methods.get(method_name)
                if method:
                    self.stack.append(obj)
                    for a in args:
                        self.stack.append(a)
                    self._call_function(method, arg_count + 1)
                    return

        # Built-in methods on primitives
        result = self._call_builtin_method(obj, method_name, args, inst.line)
        self.stack.append(result)

    def _op_new_instance(self, inst):
        cls_name = inst.arg
        cls = self.classes.get(cls_name)
        if not cls:
            raise VMError(f"Unknown class: {cls_name}", inst.line)
        self.stack.append(VMInstance(cls))

    # I/O
    def _op_print(self, inst):
        count = inst.arg
        values = []
        for _ in range(count):
            values.append(self.stack.pop())
        values.reverse()
        line = ' '.join(self._format_value(v) for v in values)
        self.output_lines.append(line)
        print(line)

    def _op_input(self, inst):
        prompt = self.stack.pop() if self.stack else ""
        self.stack.append(input(str(prompt)))

    # Iterator
    def _op_get_iter(self, inst):
        obj = self.stack.pop()
        if isinstance(obj, list):
            self.stack.append(VMIterator(obj))
        elif isinstance(obj, dict):
            self.stack.append(VMIterator(list(obj.keys())))
        elif isinstance(obj, str):
            self.stack.append(VMIterator(list(obj)))
        elif isinstance(obj, range):
            self.stack.append(VMIterator(list(obj)))
        else:
            self.stack.append(VMIterator([]))

    def _op_for_iter(self, inst):
        iterator = self.stack[-1]
        if isinstance(iterator, VMIterator) and iterator.has_next():
            self.stack.append(iterator.next())
        else:
            self.call_stack[-1].ip = inst.arg

    def _op_range(self, inst):
        args = []
        for _ in range(inst.arg):
            args.append(self.stack.pop())
        args.reverse()
        self.stack.append(range(*[int(a) for a in args]))

    # Import — full implementation
    def _op_import(self, inst):
        """Execute import by reading, parsing, and compiling the imported file."""
        filepath = inst.arg
        if filepath in self._imported_modules:
            return  # already imported
        self._imported_modules.add(filepath)

        import os
        # Try to resolve path
        abs_path = filepath
        if not os.path.isabs(filepath):
            # Try relative to current working directory
            if not filepath.endswith('.epl'):
                filepath_epl = filepath + '.epl'
            else:
                filepath_epl = filepath
            candidates = [filepath_epl, filepath,
                          os.path.join('examples', filepath_epl),
                          os.path.join('epl', 'stdlib', filepath_epl)]
            for c in candidates:
                if os.path.isfile(c):
                    abs_path = os.path.abspath(c)
                    break
            else:
                return  # file not found — silently skip (may be stdlib)

        if not os.path.isfile(abs_path):
            return

        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                source = f.read()
            from epl.lexer import Lexer
            from epl.parser import Parser
            tokens = Lexer(source).tokenize()
            program = Parser(tokens).parse()
            compiler = BytecodeCompiler()
            compiled = compiler.compile(program)
            # Execute the imported module's code in our VM
            self._exec_compiled(compiled)
        except Exception:
            pass  # Import failure is non-fatal in VM — interpreter fallback handles it

    def _exec_compiled(self, compiled):
        """Execute a compiled program's instructions, merging its functions/classes."""
        # Merge functions and classes
        for name, func in compiled.functions.items():
            self.functions[name] = func
        for name, cls in compiled.classes.items():
            self.classes[name] = cls
        # Execute top-level code
        if compiled.instructions:
            old_ip = self.call_stack[-1].ip if self.call_stack else 0
            old_code = self.call_stack[-1].code if self.call_stack else []
            frame = CallFrame(
                code=compiled.instructions,
                ip=0,
                locals={},
                name='<import>',
            )
            self.call_stack.append(frame)
            try:
                while frame.ip < len(frame.code):
                    inst = frame.code[frame.ip]
                    frame.ip += 1
                    self.instructions_executed += 1
                    result = self._dispatch(inst)
                    if result == '__HALT__':
                        break
            finally:
                self.call_stack.pop()

    # Halt
    def _op_halt(self, inst):
        return '__HALT__'

    # Exception handling
    def _op_setup_try(self, inst):
        self.try_stack.append(inst.arg)

    def _op_pop_try(self, inst):
        if self.try_stack:
            self.try_stack.pop()

    def _op_throw(self, inst):
        val = self.stack.pop()
        if self.try_stack:
            handler_ip = self.try_stack.pop()
            self.call_stack[-1].ip = handler_ip
            self.stack.append(val)
        else:
            raise VMError(str(val), inst.line)

    # ─── Closure opcodes ─────────────────────────────────────

    def _op_build_class(self, inst):
        """Define a class at runtime from stack data."""
        # BUILD_CLASS arg = class name
        # The class should already be compiled and registered
        cls_name = inst.arg
        if cls_name in self.classes:
            self.stack.append(self.classes[cls_name])
        else:
            raise VMError(f"Class '{cls_name}' not defined", inst.line)

    def _op_make_closure(self, inst):
        """Create a closure capturing free variables."""
        func_name, free_var_count = inst.arg
        # Pop the free variable values from the stack
        cells = []
        for _ in range(free_var_count):
            cells.append(self.stack.pop())
        cells.reverse()
        # Look up the function
        func = self.functions.get(func_name)
        if not func:
            frame = self.call_stack[-1]
            func = frame.locals.get(func_name)
        if not func:
            raise VMError(f"Cannot create closure: function '{func_name}' not found", inst.line)
        # Create closure wrapper
        closure = VMClosure(func, cells)
        self.stack.append(closure)

    def _op_load_free(self, inst):
        """Load a variable from the closure's captured cells."""
        frame = self.call_stack[-1]
        closure = getattr(frame, 'closure', None)
        if closure and inst.arg < len(closure.cells):
            self.stack.append(closure.cells[inst.arg])
        else:
            self.stack.append(None)

    def _op_store_free(self, inst):
        """Store a value into the closure's captured cells."""
        frame = self.call_stack[-1]
        closure = getattr(frame, 'closure', None)
        val = self.stack.pop()
        if closure and inst.arg < len(closure.cells):
            closure.cells[inst.arg] = val

    # ─── Augmented assignment opcodes ─────────────────────────

    def _op_add_assign(self, inst):
        """var += value: load var, add value, store back."""
        frame = self.call_stack[-1]
        val = self.stack.pop()
        current = frame.locals.get(inst.arg, 0)
        frame.locals[inst.arg] = current + val

    def _op_sub_assign(self, inst):
        frame = self.call_stack[-1]
        val = self.stack.pop()
        current = frame.locals.get(inst.arg, 0)
        frame.locals[inst.arg] = current - val

    def _op_mul_assign(self, inst):
        frame = self.call_stack[-1]
        val = self.stack.pop()
        current = frame.locals.get(inst.arg, 0)
        frame.locals[inst.arg] = current * val

    def _op_div_assign(self, inst):
        frame = self.call_stack[-1]
        val = self.stack.pop()
        current = frame.locals.get(inst.arg, 0)
        if val == 0:
            raise VMError("Division by zero", inst.line)
        frame.locals[inst.arg] = current / val

    # ─── Unpack opcode ────────────────────────────────────────

    def _op_unpack_seq(self, inst):
        """Unpack a sequence into n values on the stack."""
        count = inst.arg
        seq = self.stack.pop()
        items = list(seq) if not isinstance(seq, list) else seq
        if len(items) < count:
            items.extend([None] * (count - len(items)))
        # Push in reverse so first element ends up on top
        for i in range(count - 1, -1, -1):
            self.stack.append(items[i])

    # ─── Phase 6: New opcode handlers ─────────────────────────

    def _op_yield(self, inst):
        """Yield a value from a generator — push onto generator's yield list."""
        val = self.stack.pop()
        if not hasattr(self, '_yield_values'):
            self._yield_values = []
        self._yield_values.append(val)

    def _op_await(self, inst):
        """Await an async result — if it's a Future, block for result."""
        val = self.stack.pop()
        import concurrent.futures as _futures
        if isinstance(val, _futures.Future):
            try:
                result = val.result(timeout=60)
                self.stack.append(result)
            except _futures.TimeoutError:
                raise VMError("Await timed out", inst.line)
            except Exception as e:
                raise VMError(f"Async error: {e}", inst.line)
        elif hasattr(val, 'result') and callable(val.result):
            # EPLFuture or similar
            self.stack.append(val.result(timeout=60))
        else:
            # Already resolved value
            self.stack.append(val)

    def _op_call_stdlib(self, inst):
        """Call a stdlib function by name."""
        name, arg_count = inst.arg
        args = []
        for _ in range(arg_count):
            args.append(self.stack.pop())
        args.reverse()
        from epl.stdlib import call_stdlib
        result = call_stdlib(name, args, inst.line)
        self.stack.append(result)

    def _op_import_module(self, inst):
        """Full import with execution (alias form)."""
        self._op_import(inst)

    def _op_file_read(self, inst):
        """Read a file and push contents onto stack."""
        path = self.stack.pop()
        try:
            with open(str(path), 'r', encoding='utf-8') as f:
                self.stack.append(f.read())
        except (OSError, IOError) as e:
            raise VMError(f"Cannot read file: {e}", inst.line)

    def _op_super_call(self, inst):
        """Call parent class method."""
        method_name, arg_count = inst.arg
        args = []
        for _ in range(arg_count):
            args.append(self.stack.pop())
        args.reverse()
        # Find 'this' in current frame locals
        frame = self.call_stack[-1]
        this = frame.locals.get(0)  # 'this' is local 0 in methods
        if this and hasattr(this, 'klass') and hasattr(this.klass, 'parent'):
            parent = this.klass.parent
            if parent and method_name in parent.methods:
                method = parent.methods[method_name]
                result = self._call_function(method, [this] + args)
                self.stack.append(result)
                return
        # If super init, try calling parent constructor
        if method_name is None or method_name == 'init':
            if this and hasattr(this, 'klass') and this.klass.parent:
                parent = this.klass.parent
                if 'init' in parent.methods:
                    self._call_function(parent.methods['init'], [this] + args)
                    self.stack.append(None)
                    return
        self.stack.append(None)

    def _op_module_access(self, inst):
        """Access module::member."""
        module_name, member_name = inst.arg
        mod = self.globals.get(module_name)
        if isinstance(mod, dict) and member_name in mod:
            self.stack.append(mod[member_name])
        else:
            self.stack.append(None)

    # ─── Built-in functions ───────────────────────────────────

    def _init_builtins(self):
        return {
            'true': True, 'false': False, 'none': None, 'null': None,
            'yes': True, 'no': False, 'on': True, 'off': False,
            'pi': math.pi, 'euler': math.e, 'infinity': math.inf,
        }

    def _build_builtin_dispatch(self):
        """Build name → handler dict for O(1) builtin dispatch."""
        import random as _random
        import json as _json
        import os as _os

        def _length(args, line): return len(args[0]) if args else 0
        def _type_of(args, line): return self._type_name(args[0]) if args else "None"
        def _to_text(args, line): return str(args[0]) if args else ""
        def _to_number(args, line): return int(float(args[0])) if args else 0
        def _to_decimal(args, line): return float(args[0]) if args else 0.0
        def _is_number(args, line):
            try: float(args[0]); return True
            except (ValueError, TypeError): return False
        def _is_text(args, line): return isinstance(args[0], str) if args else False
        def _is_list(args, line): return isinstance(args[0], list) if args else False
        def _is_none(args, line): return args[0] is None if args else True

        # Math
        def _abs(args, line): return abs(args[0])
        def _round(args, line): return round(args[0], int(args[1])) if len(args) > 1 else round(args[0])
        def _floor(args, line): return math.floor(args[0])
        def _ceil(args, line): return math.ceil(args[0])
        def _sqrt(args, line): return math.sqrt(args[0])
        def _sin(args, line): return math.sin(args[0])
        def _cos(args, line): return math.cos(args[0])
        def _tan(args, line): return math.tan(args[0])
        def _log(args, line): return math.log(args[0])
        def _log10(args, line): return math.log10(args[0])
        def _max(args, line): return max(args[0]) if len(args) == 1 and isinstance(args[0], list) else max(args)
        def _min(args, line): return min(args[0]) if len(args) == 1 and isinstance(args[0], list) else min(args)
        def _random(args, line): return _random.random()
        def _random_int(args, line): return _random.randint(int(args[0]), int(args[1]))
        def _power(args, line): return args[0] ** args[1]

        # String
        def _upper(args, line): return str(args[0]).upper()
        def _lower(args, line): return str(args[0]).lower()
        def _trim(args, line): return str(args[0]).strip()
        def _split(args, line): return str(args[0]).split(str(args[1]) if len(args) > 1 else None)
        def _join(args, line): return str(args[1]).join(str(x) for x in args[0])
        def _replace(args, line): return str(args[0]).replace(str(args[1]), str(args[2]))
        def _contains(args, line): return str(args[1]) in str(args[0])
        def _starts_with(args, line): return str(args[0]).startswith(str(args[1]))
        def _ends_with(args, line): return str(args[0]).endswith(str(args[1]))
        def _substring(args, line):
            s = str(args[0]); start = int(args[1])
            end = int(args[2]) if len(args) > 2 else len(s)
            return s[start:end]
        def _char_at(args, line): return str(args[0])[int(args[1])]
        def _index_of(args, line): return str(args[0]).find(str(args[1]))
        def _reverse(args, line):
            if isinstance(args[0], list): return list(reversed(args[0]))
            return str(args[0])[::-1]

        # List
        def _append(args, line): args[0].append(args[1]); return args[0]
        def _pop(args, line): return args[0].pop() if isinstance(args[0], list) else None
        def _insert(args, line): args[0].insert(int(args[1]), args[2]); return args[0]
        def _remove(args, line): args[0].remove(args[1]); return args[0]
        def _sort(args, line): return sorted(args[0])
        def _range(args, line):
            if len(args) == 1: return list(range(int(args[0])))
            elif len(args) == 2: return list(range(int(args[0]), int(args[1])))
            else: return list(range(int(args[0]), int(args[1]), int(args[2])))
        def _map(args, line): return [self._call_vm_function(args[0], [x]) for x in args[1]]
        def _filter(args, line): return [x for x in args[1] if self._call_vm_function(args[0], [x])]
        def _reduce(args, line):
            func, lst = args[0], args[1]
            acc = args[2] if len(args) > 2 else lst[0]
            start = 0 if len(args) > 2 else 1
            for item in lst[start:]: acc = self._call_vm_function(func, [acc, item])
            return acc
        def _sum(args, line): return sum(args[0]) if isinstance(args[0], list) else sum(args)
        def _flatten(args, line):
            result = []
            for item in args[0]:
                if isinstance(item, list): result.extend(item)
                else: result.append(item)
            return result
        def _unique(args, line):
            seen = []
            for item in args[0]:
                if item not in seen: seen.append(item)
            return seen

        # Dict
        def _keys(args, line): return list(args[0].keys()) if isinstance(args[0], dict) else []
        def _values(args, line): return list(args[0].values()) if isinstance(args[0], dict) else []
        def _has_key(args, line): return args[1] in args[0] if isinstance(args[0], dict) else False
        def _merge(args, line): d = dict(args[0]); d.update(args[1]); return d

        # I/O
        def _read_input(args, line): return input(str(args[0]) if args else "")
        def _read_file(args, line):
            with open(str(args[0]), 'r') as f: return f.read()
        def _write_file(args, line):
            with open(str(args[0]), 'w') as f: f.write(str(args[1]))
            return True
        def _file_exists(args, line): return _os.path.exists(str(args[0]))
        def _delete_file(args, line): _os.remove(str(args[0])); return True
        def _append_file(args, line):
            with open(str(args[0]), 'a') as f: f.write(str(args[1]))
            return True

        # JSON
        def _json_parse(args, line): return _json.loads(str(args[0]))
        def _json_stringify(args, line): return _json.dumps(args[0])

        # Time
        def _time_fn(args, line): return time.time()
        def _sleep(args, line): time.sleep(float(args[0])); return None

        # Assert
        def _assert(args, line):
            if not args[0]:
                raise VMError(str(args[1]) if len(args) > 1 else "Assertion failed", line)
            return True
        def _assert_equal(args, line):
            if args[0] != args[1]:
                raise VMError(f"Expected {args[1]}, got {args[0]}", line)
            return True

        # Error
        def _error(args, line): raise VMError(str(args[0]) if args else "Error", line)

        # Conversion
        def _to_list(args, line): return list(args[0]) if args else []
        def _to_dict(args, line): return dict(args[0]) if args else {}

        dispatch = {
            # Type functions
            'length': _length, 'type_of': _type_of,
            'to_text': _to_text, 'to_string': _to_text, 'Text': _to_text,
            'to_number': _to_number, 'to_integer': _to_number, 'Integer': _to_number,
            'to_decimal': _to_decimal, 'Decimal': _to_decimal, 'Float': _to_decimal,
            'is_number': _is_number, 'is_text': _is_text, 'is_list': _is_list,
            'is_none': _is_none, 'is_null': _is_none,
            # Math
            'abs': _abs, 'absolute': _abs, 'round': _round,
            'floor': _floor, 'ceil': _ceil, 'ceiling': _ceil,
            'sqrt': _sqrt, 'sin': _sin, 'cos': _cos, 'tan': _tan,
            'log': _log, 'log10': _log10,
            'max': _max, 'min': _min,
            'random': _random, 'random_int': _random_int, 'power': _power,
            # String
            'upper': _upper, 'lower': _lower, 'trim': _trim,
            'split': _split, 'join': _join, 'replace': _replace,
            'contains': _contains, 'starts_with': _starts_with, 'ends_with': _ends_with,
            'substring': _substring, 'char_at': _char_at, 'index_of': _index_of,
            'reverse': _reverse,
            # List
            'append': _append, 'pop': _pop, 'insert': _insert, 'remove': _remove,
            'sort': _sort, 'sorted': _sort, 'range': _range,
            'map': _map, 'filter': _filter, 'reduce': _reduce,
            'sum': _sum, 'flatten': _flatten, 'unique': _unique,
            # Dict
            'keys': _keys, 'values': _values, 'has_key': _has_key, 'merge': _merge,
            # I/O
            'read_input': _read_input, 'input': _read_input,
            'read_file': _read_file, 'write_file': _write_file,
            'file_exists': _file_exists, 'delete_file': _delete_file,
            # JSON
            'json_parse': _json_parse, 'parse_json': _json_parse,
            'json_stringify': _json_stringify, 'to_json': _json_stringify,
            # Time
            'time': _time_fn, 'time_now': _time_fn, 'sleep': _sleep,
            # Assert
            'assert': _assert, 'assert_equal': _assert_equal,
            # Error
            'error': _error, 'Error': _error, 'throw': _error,
            # Conversion
            'List': _to_list, 'Dict': _to_dict,
            # Phase 6: Missing builtin aliases for interpreter parity
            'to_boolean': lambda args, line: bool(args[0]) if args else False,
            'typeof': _type_of,
            'is_integer': lambda args, line: isinstance(args[0], int) and not isinstance(args[0], bool) if args else False,
            'is_decimal': lambda args, line: isinstance(args[0], float) if args else False,
            'is_boolean': lambda args, line: isinstance(args[0], bool) if args else False,
            'is_map': lambda args, line: isinstance(args[0], dict) if args else False,
            'is_nothing': lambda args, line: args[0] is None if args else True,
            'is_none': lambda args, line: args[0] is None if args else True,
            'uppercase': _upper, 'lowercase': _lower,
            'reversed': lambda args, line: list(reversed(args[0])) if args and isinstance(args[0], list) else str(args[0])[::-1] if args else [],
            'sorted': lambda args, line: sorted(args[0]) if args else [],
            'char_code': lambda args, line: ord(str(args[0])[0]) if args and args[0] else 0,
            'from_char_code': lambda args, line: chr(int(args[0])) if args else '',
            'timestamp': _time_fn,
            'append_file': lambda args, line: _append_file(args, line),
        }

        # C FFI builtins
        try:
            from epl.ffi import ffi_open, ffi_call, ffi_close, ffi_find, ffi_types
            dispatch['ffi_open'] = lambda args, line: ffi_open(args[0]) if args else (_ for _ in ()).throw(
                ValueError("ffi_open requires a library path argument"))
            def _ffi_call_dispatch(args, line):
                if len(args) < 2:
                    raise ValueError("ffi_call requires at least (library, function_name)")
                return ffi_call(args[0], args[1],
                    args[2] if len(args) > 2 else 'void',
                    args[3] if len(args) > 3 else [],
                    args[4] if len(args) > 4 else [])
            dispatch['ffi_call'] = _ffi_call_dispatch
            dispatch['ffi_close'] = lambda args, line: ffi_close(args[0]) if args else None
            dispatch['ffi_find'] = lambda args, line: ffi_find(args[0]) if args else (_ for _ in ()).throw(
                ValueError("ffi_find requires a library name argument"))
            dispatch['ffi_types'] = lambda args, line: ffi_types()
        except ImportError:
            pass

        return dispatch

    def _exec_builtin(self, name, args, line):
        """Execute a builtin function via O(1) dict dispatch, with stdlib fallback."""
        handler = self._builtin_dispatch.get(name)
        if handler is not None:
            return handler(args, line)
        # Handle type_cast specially
        if name == 'type_cast':
            return self._type_cast(args[0], args[1]) if len(args) > 1 else args[0]
        # Phase 6: Delegate unknown builtins to stdlib
        try:
            from epl.stdlib import STDLIB_FUNCTIONS, call_stdlib
            if name in STDLIB_FUNCTIONS:
                return call_stdlib(name, args, line)
        except ImportError:
            pass
        return None

    def _call_vm_function(self, func, args):
        """Call a compiled function synchronously and return result."""
        if isinstance(func, CompiledFunction):
            # Save stack state
            stack_len = len(self.stack)
            for a in args:
                self.stack.append(a)
            self._call_function(func, len(args))
            # Run until this function returns
            while len(self.call_stack) > 1:
                frame = self.call_stack[-1]
                code = frame.func.code
                if frame.ip >= len(code):
                    self.call_stack.pop()
                    if not self.stack:
                        self.stack.append(None)
                    break
                inst = code[frame.ip]
                frame.ip += 1
                handler = self._dispatch[inst.op]
                if handler:
                    result = handler(inst)
                    if result == '__HALT__':
                        break
            return self.stack.pop() if self.stack else None
        elif callable(func):
            return func(*args)
        return None

    def _call_builtin_method(self, obj, method, args, line):
        """Handle method calls on built-in types.
        Uses direct if/elif dispatch to avoid dict/lambda allocation per call."""
        if isinstance(obj, str):
            return self._str_method(obj, method, args, line)
        elif isinstance(obj, list):
            return self._list_method(obj, method, args, line)
        elif isinstance(obj, dict):
            return self._dict_method(obj, method, args, line)
        elif isinstance(obj, (int, float)):
            return self._num_method(obj, method, args, line)
        raise VMError(f"Unknown method '{method}' on {self._type_name(obj)}", line)

    def _str_method(self, obj, method, args, line):
        if method == 'length': return len(obj)
        if method == 'upper' or method == 'to_upper': return obj.upper()
        if method == 'lower' or method == 'to_lower': return obj.lower()
        if method == 'trim' or method == 'strip': return obj.strip()
        if method == 'split': return obj.split(args[0] if args else None)
        if method == 'replace': return obj.replace(args[0], args[1])
        if method == 'contains': return args[0] in obj
        if method == 'starts_with': return obj.startswith(args[0])
        if method == 'ends_with': return obj.endswith(args[0])
        if method == 'index_of': return obj.find(args[0])
        if method == 'substring': return obj[int(args[0]):int(args[1]) if len(args) > 1 else None]
        if method == 'reverse': return obj[::-1]
        if method == 'repeat': return obj * int(args[0])
        if method == 'char_at': return obj[int(args[0])]
        if method == 'to_number' or method == 'to_integer': return int(float(obj))
        if method == 'to_decimal': return float(obj)
        if method == 'lstrip': return obj.lstrip()
        if method == 'rstrip': return obj.rstrip()
        if method == 'count': return obj.count(args[0])
        if method == 'is_empty': return len(obj) == 0
        if method == 'pad_left': return obj.rjust(int(args[0]), args[1] if len(args) > 1 else ' ')
        if method == 'pad_right': return obj.ljust(int(args[0]), args[1] if len(args) > 1 else ' ')
        raise VMError(f"Unknown method '{method}' on string", line)

    def _list_method(self, obj, method, args, line):
        if method == 'length' or method == 'count': return len(obj)
        if method == 'append' or method == 'add' or method == 'push':
            obj.append(args[0]); return obj
        if method == 'pop': return obj.pop()
        if method == 'insert': obj.insert(int(args[0]), args[1]); return obj
        if method == 'remove': obj.remove(args[0]); return obj
        if method == 'remove_at': return obj.pop(int(args[0]))
        if method == 'contains': return args[0] in obj
        if method == 'index_of': return obj.index(args[0]) if args[0] in obj else -1
        if method == 'sort': return sorted(obj)
        if method == 'reverse': return list(reversed(obj))
        if method == 'join': return (args[0] if args else ',').join(str(x) for x in obj)
        if method == 'map': return [self._call_vm_function(args[0], [x]) for x in obj]
        if method == 'filter': return [x for x in obj if self._call_vm_function(args[0], [x])]
        if method == 'reduce': return self._exec_builtin('reduce', [args[0], obj] + list(args[1:]), 0)
        if method == 'sum': return sum(obj)
        if method == 'first': return obj[0] if obj else None
        if method == 'last': return obj[-1] if obj else None
        if method == 'slice': return obj[int(args[0]):int(args[1]) if len(args) > 1 else None]
        if method == 'flatten': return [item for sublist in obj for item in (sublist if isinstance(sublist, list) else [sublist])]
        if method == 'unique': return list(dict.fromkeys(obj))
        if method == 'is_empty': return len(obj) == 0
        if method == 'clear': obj.clear(); return obj
        if method == 'copy': return list(obj)
        if method == 'each': return [self._call_vm_function(args[0], [x]) for x in obj]
        if method == 'find': return next((x for x in obj if self._call_vm_function(args[0], [x])), None)
        if method == 'every': return all(self._call_vm_function(args[0], [x]) for x in obj)
        if method == 'some': return any(self._call_vm_function(args[0], [x]) for x in obj)
        raise VMError(f"Unknown method '{method}' on list", line)

    def _dict_method(self, obj, method, args, line):
        if method == 'keys': return list(obj.keys())
        if method == 'values': return list(obj.values())
        if method == 'items': return [[k, v] for k, v in obj.items()]
        if method == 'has_key': return args[0] in obj
        if method == 'get': return obj.get(args[0], args[1] if len(args) > 1 else None)
        if method == 'set': obj[args[0]] = args[1]; return obj
        if method == 'remove': obj.pop(args[0], None); return obj
        if method == 'merge': return {**obj, **args[0]}
        if method == 'length': return len(obj)
        if method == 'is_empty': return len(obj) == 0
        if method == 'clear': obj.clear(); return obj
        if method == 'copy': return dict(obj)
        if method == 'to_json': return __import__('json').dumps(obj)
        raise VMError(f"Unknown method '{method}' on dict", line)

    def _num_method(self, obj, method, args, line):
        if method == 'to_text' or method == 'to_string': return str(obj)
        if method == 'abs': return abs(obj)
        if method == 'round': return round(obj, int(args[0])) if args else round(obj)
        if method == 'floor': return math.floor(obj)
        if method == 'ceil': return math.ceil(obj)
        if method == 'is_even': return obj % 2 == 0
        if method == 'is_odd': return obj % 2 != 0
        if method == 'clamp': return max(args[0], min(obj, args[1]))
        raise VMError(f"Unknown method '{method}' on {self._type_name(obj)}", line)

    def _type_cast(self, val, target):
        """Cast value to target type."""
        if target in ('Integer', 'Int', 'int'):
            return int(float(val)) if val is not None else 0
        elif target in ('Decimal', 'Float', 'float'):
            return float(val) if val is not None else 0.0
        elif target in ('Text', 'String', 'str'):
            return str(val) if val is not None else ""
        elif target in ('Boolean', 'Bool', 'bool'):
            return bool(val)
        elif target in ('List', 'list'):
            return list(val) if val is not None else []
        return val

    def _format_value(self, val):
        """Format a value for output."""
        if val is None:
            return "none"
        elif isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, float):
            if val == int(val):
                return str(int(val))
            return str(val)
        elif isinstance(val, list):
            return '[' + ', '.join(self._format_value(v) for v in val) + ']'
        elif isinstance(val, dict):
            items = ', '.join(f'{k}: {self._format_value(v)}' for k, v in val.items())
            return '{' + items + '}'
        elif isinstance(val, VMInstance):
            attrs = ', '.join(f'{k}: {self._format_value(v)}' for k, v in val.attrs.items())
            return f"{val.class_def.name}({attrs})"
        elif isinstance(val, CompiledFunction):
            return f"<function {val.name}>"
        elif isinstance(val, CompiledClass):
            return f"<class {val.name}>"
        return str(val)

    def _type_name(self, val):
        """Get EPL type name for a value."""
        if val is None:
            return "None"
        elif isinstance(val, bool):
            return "Boolean"
        elif isinstance(val, int):
            return "Integer"
        elif isinstance(val, float):
            return "Decimal"
        elif isinstance(val, str):
            return "Text"
        elif isinstance(val, list):
            return "List"
        elif isinstance(val, dict):
            return "Dict"
        elif isinstance(val, VMInstance):
            return val.class_def.name
        elif isinstance(val, CompiledFunction):
            return "Function"
        elif isinstance(val, CompiledClass):
            return "Class"
        return "Unknown"


# ─── Convenience functions ────────────────────────────────────

def compile_and_run(source: str) -> dict:
    """Compile and execute EPL source code using the bytecode VM."""
    from epl.lexer import Lexer
    from epl.parser import Parser

    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()

    compiler = BytecodeCompiler()
    compiled = compiler.compile(program)

    vm = VM()
    result = vm.execute(compiled)
    return result


def compile_to_bytecode(source: str) -> dict:
    """Compile EPL source to bytecode without execution."""
    from epl.lexer import Lexer
    from epl.parser import Parser

    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()

    compiler = BytecodeCompiler()
    return compiler.compile(program)


def disassemble(source: str) -> str:
    """Compile EPL source and return human-readable bytecode disassembly."""
    from epl.lexer import Lexer
    from epl.parser import Parser

    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()

    compiler = BytecodeCompiler()
    compiler.compile(program)
    return compiler.disassemble()
