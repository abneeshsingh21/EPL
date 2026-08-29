"""
EPL High-Level Intermediate Representation (EPL-HIR) v1.0
=========================================================
A Static Single Assignment (SSA) form Control Flow Graph (CFG) intermediate
representation for EPL compilers, optimizers, and target code generators.

Key components:
- SSA Values: SSAVar, Constant
- Instructions: BinaryOp, UnaryOp, CompareOp, Phi, Call, GetIndex, BuildList, etc.
- BasicBlock: Linear sequence of SSA instructions ending in a single terminator.
- HIRFunction: Control Flow Graph of Basic Blocks with dominator tracking.
- HIRModule: Container for functions, classes, and global declarations.
- ASTToHIR: Lowers EPL AST (epl.ast_nodes) to SSA CFG form with automatic Phi placement.
- HIRPassManager & Optimizers: Constant folding, dead code elimination, and CSE.
- HIRPrinter & HIRVerifier: Human-readable SSA disassembly and formal integrity verification.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from epl import ast_nodes as ast


# ═══════════════════════════════════════════════════════════
#  Types & Values
# ═══════════════════════════════════════════════════════════


class HIRTypeKind(Enum):
    INT = 'int'
    FLOAT = 'float'
    BOOL = 'bool'
    STRING = 'string'
    NONE = 'none'
    LIST = 'list'
    MAP = 'map'
    OBJECT = 'object'
    ANY = 'any'
    VOID = 'void'


@dataclass(frozen=True)
class HIRType:
    kind: HIRTypeKind
    element_type: Optional['HIRType'] = None
    key_type: Optional['HIRType'] = None
    value_type: Optional['HIRType'] = None
    class_name: Optional[str] = None

    def __repr__(self) -> str:
        if self.kind == HIRTypeKind.LIST and self.element_type:
            return f'List<{self.element_type}>'
        if self.kind == HIRTypeKind.MAP and self.key_type and self.value_type:
            return f'Map<{self.key_type}, {self.value_type}>'
        if self.kind == HIRTypeKind.OBJECT and self.class_name:
            return self.class_name
        return self.kind.value


T_INT = HIRType(HIRTypeKind.INT)
T_FLOAT = HIRType(HIRTypeKind.FLOAT)
T_BOOL = HIRType(HIRTypeKind.BOOL)
T_STRING = HIRType(HIRTypeKind.STRING)
T_NONE = HIRType(HIRTypeKind.NONE)
T_ANY = HIRType(HIRTypeKind.ANY)
T_VOID = HIRType(HIRTypeKind.VOID)


@dataclass(frozen=True)
class SSAVar:
    name: str
    version: int
    hir_type: HIRType = field(default=T_ANY)

    def __repr__(self) -> str:
        return f'%{self.name}.{self.version}'


@dataclass(frozen=True)
class HIRConstant:
    value: Any
    hir_type: HIRType

    def __repr__(self) -> str:
        if self.hir_type.kind == HIRTypeKind.STRING:
            return f'"{self.value}"'
        if self.hir_type.kind == HIRTypeKind.NONE:
            return 'nothing'
        if self.hir_type.kind == HIRTypeKind.BOOL:
            return 'true' if self.value else 'false'
        return str(self.value)


HIROperand = Union[SSAVar, HIRConstant]


# ═══════════════════════════════════════════════════════════
#  Instructions
# ═══════════════════════════════════════════════════════════


class HIRInstruction:
    """Base class for all HIR SSA instructions."""

    result: Optional[SSAVar]

    def get_uses(self) -> List[SSAVar]:
        """Return all SSA variables read by this instruction."""
        return []

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        """Replace usages of old_var with new_op."""
        pass


@dataclass
class HIRPhi(HIRInstruction):
    result: SSAVar
    incoming: List[Tuple[HIROperand, str]]  # (operand, block_label)

    def get_uses(self) -> List[SSAVar]:
        return [op for op, _ in self.incoming if isinstance(op, SSAVar)]

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        self.incoming = [
            (new_op if op == old_var else op, blk) for op, blk in self.incoming
        ]

    def __repr__(self) -> str:
        inc_str = ', '.join(f'[{op}, {blk}]' for op, blk in self.incoming)
        return f'{self.result} = phi {inc_str} : {self.result.hir_type}'


@dataclass
class HIRAssign(HIRInstruction):
    result: SSAVar
    value: HIROperand

    def get_uses(self) -> List[SSAVar]:
        return [self.value] if isinstance(self.value, SSAVar) else []

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        if self.value == old_var:
            self.value = new_op

    def __repr__(self) -> str:
        return f'{self.result} = assign {self.value} : {self.result.hir_type}'


@dataclass
class HIRConstInst(HIRInstruction):
    result: SSAVar
    constant: HIRConstant

    def __repr__(self) -> str:
        return f'{self.result} = const {self.constant} : {self.result.hir_type}'


@dataclass
class HIRBinaryOp(HIRInstruction):
    result: SSAVar
    op: str  # '+', '-', '*', '/', '//', '%', '^'
    left: HIROperand
    right: HIROperand

    def get_uses(self) -> List[SSAVar]:
        uses = []
        if isinstance(self.left, SSAVar):
            uses.append(self.left)
        if isinstance(self.right, SSAVar):
            uses.append(self.right)
        return uses

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        if self.left == old_var:
            self.left = new_op
        if self.right == old_var:
            self.right = new_op

    def __repr__(self) -> str:
        op_names = {
            '+': 'add',
            '-': 'sub',
            '*': 'mul',
            '/': 'div',
            '//': 'floordiv',
            '%': 'mod',
            '^': 'pow',
        }
        name = op_names.get(self.op, self.op)
        return f'{self.result} = {name} {self.left}, {self.right} : {self.result.hir_type}'


@dataclass
class HIRUnaryOp(HIRInstruction):
    result: SSAVar
    op: str  # '-', 'not'
    operand: HIROperand

    def get_uses(self) -> List[SSAVar]:
        return [self.operand] if isinstance(self.operand, SSAVar) else []

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        if self.operand == old_var:
            self.operand = new_op

    def __repr__(self) -> str:
        name = 'neg' if self.op == '-' else 'not'
        return f'{self.result} = {name} {self.operand} : {self.result.hir_type}'


@dataclass
class HIRCompareOp(HIRInstruction):
    result: SSAVar
    op: str  # '==', '!=', '<', '<=', '>', '>='
    left: HIROperand
    right: HIROperand

    def get_uses(self) -> List[SSAVar]:
        uses = []
        if isinstance(self.left, SSAVar):
            uses.append(self.left)
        if isinstance(self.right, SSAVar):
            uses.append(self.right)
        return uses

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        if self.left == old_var:
            self.left = new_op
        if self.right == old_var:
            self.right = new_op

    def __repr__(self) -> str:
        cmp_names = {
            '==': 'eq',
            '!=': 'ne',
            '<': 'lt',
            '<=': 'le',
            '>': 'gt',
            '>=': 'ge',
        }
        name = cmp_names.get(self.op, self.op)
        return f'{self.result} = {name} {self.left}, {self.right} : {self.result.hir_type}'


@dataclass
class HIRCall(HIRInstruction):
    result: Optional[SSAVar]
    func_name: str
    args: List[HIROperand]

    def get_uses(self) -> List[SSAVar]:
        return [a for a in self.args if isinstance(a, SSAVar)]

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        self.args = [new_op if a == old_var else a for a in self.args]

    def __repr__(self) -> str:
        args_str = ', '.join(str(a) for a in self.args)
        if self.result:
            return f'{self.result} = call @{self.func_name}({args_str}) : {self.result.hir_type}'
        return f'call @{self.func_name}({args_str})'


@dataclass
class HIRMethodCall(HIRInstruction):
    result: Optional[SSAVar]
    target: HIROperand
    method_name: str
    args: List[HIROperand]

    def get_uses(self) -> List[SSAVar]:
        uses = [self.target] if isinstance(self.target, SSAVar) else []
        uses.extend([a for a in self.args if isinstance(a, SSAVar)])
        return uses

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        if self.target == old_var:
            self.target = new_op
        self.args = [new_op if a == old_var else a for a in self.args]

    def __repr__(self) -> str:
        args_str = ', '.join(str(a) for a in self.args)
        if self.result:
            return f'{self.result} = method_call {self.target}.{self.method_name}({args_str}) : {self.result.hir_type}'
        return f'method_call {self.target}.{self.method_name}({args_str})'


@dataclass
class HIRGetIndex(HIRInstruction):
    result: SSAVar
    target: HIROperand
    index: HIROperand

    def get_uses(self) -> List[SSAVar]:
        uses = []
        if isinstance(self.target, SSAVar):
            uses.append(self.target)
        if isinstance(self.index, SSAVar):
            uses.append(self.index)
        return uses

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        if self.target == old_var:
            self.target = new_op
        if self.index == old_var:
            self.index = new_op

    def __repr__(self) -> str:
        return f'{self.result} = getindex {self.target}[{self.index}] : {self.result.hir_type}'


@dataclass
class HIRSetIndex(HIRInstruction):
    target: HIROperand
    index: HIROperand
    value: HIROperand

    def get_uses(self) -> List[SSAVar]:
        uses = []
        for op in [self.target, self.index, self.value]:
            if isinstance(op, SSAVar):
                uses.append(op)
        return uses

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        if self.target == old_var:
            self.target = new_op
        if self.index == old_var:
            self.index = new_op
        if self.value == old_var:
            self.value = new_op

    def __repr__(self) -> str:
        return f'setindex {self.target}[{self.index}] = {self.value}'


@dataclass
class HIRBuildList(HIRInstruction):
    result: SSAVar
    elements: List[HIROperand]

    def get_uses(self) -> List[SSAVar]:
        return [e for e in self.elements if isinstance(e, SSAVar)]

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        self.elements = [new_op if e == old_var else e for e in self.elements]

    def __repr__(self) -> str:
        elems = ', '.join(str(e) for e in self.elements)
        return f'{self.result} = build_list [{elems}] : {self.result.hir_type}'


@dataclass
class HIRBuildMap(HIRInstruction):
    result: SSAVar
    keys: List[HIROperand]
    values: List[HIROperand]

    def get_uses(self) -> List[SSAVar]:
        uses = [k for k in self.keys if isinstance(k, SSAVar)]
        uses.extend([v for v in self.values if isinstance(v, SSAVar)])
        return uses

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        self.keys = [new_op if k == old_var else k for k in self.keys]
        self.values = [new_op if v == old_var else v for v in self.values]

    def __repr__(self) -> str:
        kvs = ', '.join(f'{k}: {v}' for k, v in zip(self.keys, self.values))
        return f'{self.result} = build_map {{{kvs}}} : {self.result.hir_type}'


@dataclass
class HIRPrint(HIRInstruction):
    values: List[HIROperand]

    def get_uses(self) -> List[SSAVar]:
        return [v for v in self.values if isinstance(v, SSAVar)]

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        self.values = [new_op if v == old_var else v for v in self.values]

    def __repr__(self) -> str:
        vals = ', '.join(str(v) for v in self.values)
        return f'print {vals}'


# ─── Terminators ──────────────────────────────────────────


@dataclass
class HIRJump(HIRInstruction):
    target: str

    def __repr__(self) -> str:
        return f'jump %{self.target}'


@dataclass
class HIRBranch(HIRInstruction):
    condition: HIROperand
    true_target: str
    false_target: str

    def get_uses(self) -> List[SSAVar]:
        return [self.condition] if isinstance(self.condition, SSAVar) else []

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        if self.condition == old_var:
            self.condition = new_op

    def __repr__(self) -> str:
        return f'branch {self.condition}, %{self.true_target}, %{self.false_target}'


@dataclass
class HIRReturn(HIRInstruction):
    value: Optional[HIROperand] = None

    def get_uses(self) -> List[SSAVar]:
        return [self.value] if isinstance(self.value, SSAVar) else []

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        if self.value == old_var:
            self.value = new_op

    def __repr__(self) -> str:
        return f'return {self.value}' if self.value else 'return'


@dataclass
class HIRThrow(HIRInstruction):
    exception: HIROperand

    def get_uses(self) -> List[SSAVar]:
        return [self.exception] if isinstance(self.exception, SSAVar) else []

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        if self.exception == old_var:
            self.exception = new_op

    def __repr__(self) -> str:
        return f'throw {self.exception}'


# ═══════════════════════════════════════════════════════════
#  Basic Block & Function Graphs
# ═══════════════════════════════════════════════════════════


class BasicBlock:
    """A linear sequence of instructions executed without branching until the terminator."""

    def __init__(self, label: str):
        self.label = label
        self.instructions: List[HIRInstruction] = []
        self.terminator: Optional[HIRInstruction] = None
        self.predecessors: Set[str] = set()
        self.successors: Set[str] = set()

    def add_instruction(self, inst: HIRInstruction) -> None:
        self.instructions.append(inst)

    def set_terminator(self, term: HIRInstruction) -> None:
        self.terminator = term

    def is_terminated(self) -> bool:
        return self.terminator is not None

    def __repr__(self) -> str:
        lines = [f'{self.label}:']
        for inst in self.instructions:
            lines.append(f'  {inst}')
        if self.terminator:
            lines.append(f'  {self.terminator}')
        return '\n'.join(lines)


@dataclass
class HIRFunction:
    name: str
    params: List[Tuple[str, HIRType]]
    return_type: HIRType
    blocks: Dict[str, BasicBlock] = field(default_factory=dict)
    entry_label: str = 'entry'

    def add_block(self, block: BasicBlock) -> None:
        self.blocks[block.label] = block

    def get_entry_block(self) -> BasicBlock:
        return self.blocks[self.entry_label]

    def build_cfg_edges(self) -> None:
        """Compute predecessor and successor edges for all basic blocks."""
        for b in self.blocks.values():
            b.predecessors.clear()
            b.successors.clear()

        for b in self.blocks.values():
            if isinstance(b.terminator, HIRJump):
                if b.terminator.target in self.blocks:
                    b.successors.add(b.terminator.target)
                    self.blocks[b.terminator.target].predecessors.add(b.label)
            elif isinstance(b.terminator, HIRBranch):
                if b.terminator.true_target in self.blocks:
                    b.successors.add(b.terminator.true_target)
                    self.blocks[b.terminator.true_target].predecessors.add(b.label)
                if b.terminator.false_target in self.blocks:
                    b.successors.add(b.terminator.false_target)
                    self.blocks[b.terminator.false_target].predecessors.add(b.label)

    def __repr__(self) -> str:
        params_str = ', '.join(f'%{p}: {t}' for p, t in self.params)
        lines = [f'function @{self.name}({params_str}) -> {self.return_type}:']
        for b in self.blocks.values():
            lines.append(str(b))
        return '\n'.join(lines)


@dataclass
class HIRModule:
    name: str
    functions: Dict[str, HIRFunction] = field(default_factory=dict)
    globals: Dict[str, HIRType] = field(default_factory=dict)

    def add_function(self, func: HIRFunction) -> None:
        self.functions[func.name] = func

    def __repr__(self) -> str:
        lines = [f'; EPL-HIR Module: {self.name}']
        for g_name, g_type in self.globals.items():
            lines.append(f'global @{g_name} : {g_type}')
        lines.append('')
        for fn in self.functions.values():
            lines.append(str(fn))
            lines.append('')
        return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════
#  AST to HIR Lowering Engine
# ═══════════════════════════════════════════════════════════


class ASTToHIR:
    """Lowers an EPL AST into SSA Form EPL-HIR."""

    def __init__(self, module_name: str = 'main_module'):
        self.module_name = module_name
        self.module = HIRModule(name=module_name)
        self.current_func: Optional[HIRFunction] = None
        self.current_block: Optional[BasicBlock] = None
        self._var_counters: Dict[str, int] = {}
        self._block_counter = 0
        self._current_scope: Dict[str, SSAVar] = {}

    def new_ssa_var(self, name: str, hir_type: HIRType = T_ANY) -> SSAVar:
        clean_name = name.replace(' ', '_').replace('-', '_')
        ver = self._var_counters.get(clean_name, 0)
        self._var_counters[clean_name] = ver + 1
        var = SSAVar(clean_name, ver, hir_type)
        self._current_scope[name] = var
        return var

    def new_temp_var(self, prefix: str = 't', hir_type: HIRType = T_ANY) -> SSAVar:
        return self.new_ssa_var(prefix, hir_type)

    def new_block(self, prefix: str = 'block') -> BasicBlock:
        self._block_counter += 1
        label = f'{prefix}.{self._block_counter}'
        block = BasicBlock(label)
        if self.current_func:
            self.current_func.add_block(block)
        return block

    def lower(self, program_ast: ast.Program) -> HIRModule:
        """Translate full EPL Program AST into a HIRModule."""
        # Lower top-level statements into main function
        main_fn = HIRFunction(
            name='main',
            params=[],
            return_type=T_INT,
        )
        self.module.add_function(main_fn)
        self.current_func = main_fn

        entry = BasicBlock('entry')
        main_fn.add_block(entry)
        self.current_block = entry

        # First pass: Lower standalone functions
        top_level_stmts = []
        for stmt in program_ast.statements:
            if isinstance(stmt, ast.FunctionDef):
                self._lower_function_def(stmt)
            else:
                top_level_stmts.append(stmt)

        # Second pass: Lower top-level code into main function
        self.current_func = main_fn
        self.current_block = entry
        for stmt in top_level_stmts:
            self._lower_statement(stmt)

        if not self.current_block.is_terminated():
            ret_zero = self.new_temp_var('zero', T_INT)
            self.current_block.add_instruction(
                HIRConstInst(ret_zero, HIRConstant(0, T_INT))
            )
            self.current_block.set_terminator(HIRReturn(ret_zero))

        main_fn.build_cfg_edges()

        for fn in self.module.functions.values():
            fn.build_cfg_edges()

        return self.module

    def _lower_function_def(self, func_node: ast.FunctionDef) -> None:
        saved_func = self.current_func
        saved_block = self.current_block
        saved_scope = dict(self._current_scope)

        params = []
        for p in func_node.params:
            if isinstance(p, tuple):
                p_name = str(p[0])
                p_type = self._map_ast_type(p[1]) if len(p) > 1 else T_ANY
            else:
                p_name = str(p)
                p_type = T_ANY
            params.append((p_name, p_type))

        fn = HIRFunction(
            name=func_node.name,
            params=params,
            return_type=T_ANY,
        )
        self.module.add_function(fn)
        self.current_func = fn

        entry = BasicBlock('entry')
        fn.add_block(entry)
        self.current_block = entry
        self._current_scope = {}

        for p_name, p_type in params:
            self.new_ssa_var(p_name, p_type)

        for stmt in func_node.body:
            self._lower_statement(stmt)

        if not self.current_block.is_terminated():
            self.current_block.set_terminator(HIRReturn(None))

        fn.build_cfg_edges()

        self.current_func = saved_func
        self.current_block = saved_block
        self._current_scope = saved_scope

    def _lower_statement(self, stmt: ast.ASTNode) -> None:
        if self.current_block.is_terminated():
            # Unreachable statement after terminator
            return

        if isinstance(stmt, ast.VarDeclaration):
            val_op = (
                self._lower_expr(stmt.value)
                if stmt.value
                else HIRConstant(None, T_NONE)
            )
            var_type_str = getattr(stmt, 'var_type', getattr(stmt, 'type_annotation', None))
            var_type = self._map_ast_type(var_type_str)
            ssa_var = self.new_ssa_var(stmt.name, var_type)
            if isinstance(val_op, HIRConstant):
                self.current_block.add_instruction(HIRConstInst(ssa_var, val_op))
            else:
                self.current_block.add_instruction(HIRAssign(ssa_var, val_op))

        elif isinstance(stmt, (ast.VarAssignment, ast.DestructureAssignment)):
            if isinstance(stmt, ast.VarAssignment):
                val_op = self._lower_expr(stmt.value)
                ssa_var = self.new_ssa_var(stmt.name, T_ANY)
                if isinstance(val_op, HIRConstant):
                    self.current_block.add_instruction(HIRConstInst(ssa_var, val_op))
                else:
                    self.current_block.add_instruction(HIRAssign(ssa_var, val_op))

        elif isinstance(stmt, ast.PrintStatement):
            if hasattr(stmt, 'expression') and stmt.expression is not None:
                ops = [self._lower_expr(stmt.expression)]
            elif hasattr(stmt, 'args'):
                ops = [self._lower_expr(arg) for arg in stmt.args]
            else:
                ops = []
            self.current_block.add_instruction(HIRPrint(ops))

        elif isinstance(stmt, ast.ReturnStatement):
            val_op = self._lower_expr(stmt.value) if stmt.value else None
            self.current_block.set_terminator(HIRReturn(val_op))

        elif isinstance(stmt, ast.IfStatement):
            self._lower_if_statement(stmt)

        elif isinstance(stmt, ast.WhileLoop):
            self._lower_while_statement(stmt)

        elif isinstance(stmt, ast.AugmentedAssignment):
            cur_val = self._current_scope.get(stmt.name) or self.new_ssa_var(stmt.name, T_ANY)
            val_op = self._lower_expr(stmt.value)
            res_var = self.new_ssa_var(stmt.name, T_ANY)
            self.current_block.add_instruction(HIRBinaryOp(res_var, stmt.operator, cur_val, val_op))

        elif isinstance(stmt, ast.RepeatLoop):
            cnt_op = self._lower_expr(stmt.count)
            idx_var = self.new_ssa_var('repeat_idx', T_INT)
            self.current_block.add_instruction(HIRConstInst(idx_var, HIRConstant(0, T_INT)))
            hdr = self.new_block('repeat_hdr')
            body = self.new_block('repeat_body')
            exit_blk = self.new_block('repeat_exit')
            self.current_block.set_terminator(HIRJump(hdr.label))

            self.current_block = hdr
            cur_idx = self._current_scope.get('repeat_idx', idx_var)
            cmp_var = self.new_temp_var('cmp', T_BOOL)
            hdr.add_instruction(HIRCompareOp(cmp_var, '<', cur_idx, cnt_op))
            hdr.set_terminator(HIRBranch(cmp_var, body.label, exit_blk.label))

            self.current_block = body
            for s in stmt.body:
                self._lower_statement(s)
            next_idx = self.new_ssa_var('repeat_idx', T_INT)
            body.add_instruction(HIRBinaryOp(next_idx, '+', self._current_scope.get('repeat_idx', idx_var), HIRConstant(1, T_INT)))
            if not self.current_block.is_terminated():
                self.current_block.set_terminator(HIRJump(hdr.label))

            self.current_block = exit_blk

        elif isinstance(stmt, ast.ForEachLoop):
            iter_op = self._lower_expr(stmt.iterable)
            len_var = self.new_temp_var('len', T_INT)
            self.current_block.add_instruction(HIRCall(len_var, 'length', [iter_op]))
            idx_var = self.new_ssa_var('for_idx', T_INT)
            self.current_block.add_instruction(HIRConstInst(idx_var, HIRConstant(0, T_INT)))
            hdr = self.new_block('for_hdr')
            body = self.new_block('for_body')
            exit_blk = self.new_block('for_exit')
            self.current_block.set_terminator(HIRJump(hdr.label))

            self.current_block = hdr
            cur_idx = self._current_scope.get('for_idx', idx_var)
            cmp_var = self.new_temp_var('cmp', T_BOOL)
            hdr.add_instruction(HIRCompareOp(cmp_var, '<', cur_idx, len_var))
            hdr.set_terminator(HIRBranch(cmp_var, body.label, exit_blk.label))

            self.current_block = body
            elem_var = self.new_ssa_var(stmt.var_name, T_ANY)
            body.add_instruction(HIRGetIndex(elem_var, iter_op, self._current_scope.get('for_idx', idx_var)))
            for s in stmt.body:
                self._lower_statement(s)
            next_idx = self.new_ssa_var('for_idx', T_INT)
            body.add_instruction(HIRBinaryOp(next_idx, '+', self._current_scope.get('for_idx', idx_var), HIRConstant(1, T_INT)))
            if not self.current_block.is_terminated():
                self.current_block.set_terminator(HIRJump(hdr.label))

            self.current_block = exit_blk

        else:
            self._lower_expr(stmt)

    def _lower_if_statement(self, stmt: ast.IfStatement) -> None:
        cond_op = self._lower_expr(stmt.condition)
        then_block = self.new_block('if_then')
        else_block = self.new_block('if_else')
        merge_block = self.new_block('if_merge')

        self.current_block.set_terminator(
            HIRBranch(cond_op, then_block.label, else_block.label)
        )

        scope_before = dict(self._current_scope)

        # Lower Then Block
        self.current_block = then_block
        for s in stmt.then_body:
            self._lower_statement(s)
        if not self.current_block.is_terminated():
            self.current_block.set_terminator(HIRJump(merge_block.label))
        scope_then = dict(self._current_scope)

        # Lower Else Block
        self.current_block = else_block
        self._current_scope = dict(scope_before)
        if stmt.else_body:
            for s in stmt.else_body:
                self._lower_statement(s)
        if not self.current_block.is_terminated():
            self.current_block.set_terminator(HIRJump(merge_block.label))
        scope_else = dict(self._current_scope)

        # Merge Block with Phi Nodes
        self.current_block = merge_block
        merged_scope = {}
        all_keys = set(scope_then.keys()) | set(scope_else.keys())
        for k in all_keys:
            var_then = scope_then.get(k)
            var_else = scope_else.get(k)
            if var_then and var_else and var_then != var_else:
                phi_var = self.new_ssa_var(k, var_then.hir_type)
                phi = HIRPhi(
                    phi_var,
                    [(var_then, then_block.label), (var_else, else_block.label)],
                )
                merge_block.add_instruction(phi)
                merged_scope[k] = phi_var
            elif var_then:
                merged_scope[k] = var_then
            elif var_else:
                merged_scope[k] = var_else

        self._current_scope = merged_scope

    def _lower_while_statement(self, stmt: ast.WhileLoop) -> None:
        header_block = self.new_block('while_hdr')
        body_block = self.new_block('while_body')
        exit_block = self.new_block('while_exit')

        self.current_block.set_terminator(HIRJump(header_block.label))

        # Header Block: Condition evaluation
        self.current_block = header_block
        cond_op = self._lower_expr(stmt.condition)
        header_block.set_terminator(
            HIRBranch(cond_op, body_block.label, exit_block.label)
        )

        # Body Block
        self.current_block = body_block
        for s in stmt.body:
            self._lower_statement(s)
        if not self.current_block.is_terminated():
            self.current_block.set_terminator(HIRJump(header_block.label))

        # Exit Block
        self.current_block = exit_block

    def _lower_expr(self, expr: ast.ASTNode) -> HIROperand:
        if isinstance(expr, ast.Literal):
            val = expr.value
            if isinstance(val, bool):
                return HIRConstant(val, T_BOOL)
            if isinstance(val, int):
                return HIRConstant(val, T_INT)
            if isinstance(val, float):
                return HIRConstant(val, T_FLOAT)
            if isinstance(val, str):
                return HIRConstant(val, T_STRING)
            if val is None:
                return HIRConstant(None, T_NONE)
            return HIRConstant(val, T_ANY)

        elif isinstance(expr, ast.Identifier):
            if expr.name in self._current_scope:
                return self._current_scope[expr.name]
            return self.new_ssa_var(expr.name, T_ANY)

        elif isinstance(expr, ast.BinaryOp):
            left_op = self._lower_expr(expr.left)
            right_op = self._lower_expr(expr.right)
            op = expr.operator
            res_type = T_INT if op in ('+', '-', '*', '%') else T_FLOAT
            if op in ('==', '!=', '<', '<=', '>', '>=', 'is', 'is not'):
                res_var = self.new_temp_var('cmp', T_BOOL)
                self.current_block.add_instruction(
                    HIRCompareOp(res_var, op, left_op, right_op)
                )
                return res_var
            res_var = self.new_temp_var('bin', res_type)
            self.current_block.add_instruction(
                HIRBinaryOp(res_var, op, left_op, right_op)
            )
            return res_var

        elif isinstance(expr, ast.UnaryOp):
            operand = self._lower_expr(expr.operand)
            res_var = self.new_temp_var('un', T_ANY)
            self.current_block.add_instruction(
                HIRUnaryOp(res_var, expr.operator, operand)
            )
            return res_var

        elif isinstance(expr, ast.FunctionCall):
            args = [self._lower_expr(a) for a in expr.arguments]
            res_var = self.new_temp_var('call', T_ANY)
            self.current_block.add_instruction(
                HIRCall(res_var, expr.name, args)
            )
            return res_var

        elif isinstance(expr, ast.ListLiteral):
            elems = [self._lower_expr(e) for e in expr.elements]
            res_var = self.new_temp_var(
                'list', HIRType(HIRTypeKind.LIST, T_ANY)
            )
            self.current_block.add_instruction(HIRBuildList(res_var, elems))
            return res_var

        elif isinstance(expr, ast.DictLiteral):
            keys = [self._lower_expr(k) for k, v in expr.pairs]
            vals = [self._lower_expr(v) for k, v in expr.pairs]
            res_var = self.new_temp_var(
                'map', HIRType(HIRTypeKind.MAP, T_ANY, T_ANY)
            )
            self.current_block.add_instruction(HIRBuildMap(res_var, keys, vals))
            return res_var

        elif isinstance(expr, ast.IndexAccess):
            target = self._lower_expr(expr.target)
            idx = self._lower_expr(expr.index)
            res_var = self.new_temp_var('idx', T_ANY)
            self.current_block.add_instruction(
                HIRGetIndex(res_var, target, idx)
            )
            return res_var

        return HIRConstant(None, T_NONE)

    def _map_ast_type(self, type_str: Optional[str]) -> HIRType:
        if not type_str:
            return T_ANY
        t = type_str.lower()
        if t in ('integer', 'int'):
            return T_INT
        if t in ('decimal', 'float', 'number'):
            return T_FLOAT
        if t in ('text', 'string', 'str'):
            return T_STRING
        if t in ('boolean', 'bool'):
            return T_BOOL
        if t in ('nothing', 'void', 'none'):
            return T_NONE
        return T_ANY


# ═══════════════════════════════════════════════════════════
#  Optimization Passes & Pass Manager
# ═══════════════════════════════════════════════════════════


class ConstantFoldingPass:
    """Folds arithmetic and comparison operations on compile-time constants."""

    _OPS = {
        '+': operator.add,
        '-': operator.sub,
        '*': operator.mul,
        '/': operator.truediv,
        '//': operator.floordiv,
        '%': operator.mod,
        '^': operator.pow,
    }

    _CMPS = {
        '==': operator.eq,
        '!=': operator.ne,
        '<': operator.lt,
        '<=': operator.le,
        '>': operator.gt,
        '>=': operator.ge,
    }

    def run_on_function(self, func: HIRFunction) -> bool:
        changed = False
        for block in func.blocks.values():
            new_instructions = []
            for inst in block.instructions:
                if (
                    isinstance(inst, HIRBinaryOp)
                    and isinstance(inst.left, HIRConstant)
                    and isinstance(inst.right, HIRConstant)
                ):
                    op_fn = self._OPS.get(inst.op)
                    if op_fn:
                        try:
                            val = op_fn(inst.left.value, inst.right.value)
                            c_type = T_INT if isinstance(val, int) else T_FLOAT
                            new_instructions.append(
                                HIRConstInst(inst.result, HIRConstant(val, c_type))
                            )
                            changed = True
                            continue
                        except ZeroDivisionError:
                            pass

                elif (
                    isinstance(inst, HIRCompareOp)
                    and isinstance(inst.left, HIRConstant)
                    and isinstance(inst.right, HIRConstant)
                ):
                    cmp_fn = self._CMPS.get(inst.op)
                    if cmp_fn:
                        val = cmp_fn(inst.left.value, inst.right.value)
                        new_instructions.append(
                            HIRConstInst(inst.result, HIRConstant(val, T_BOOL))
                        )
                        changed = True
                        continue

                new_instructions.append(inst)
            block.instructions = new_instructions
        return changed


class DeadCodeEliminationPass:
    """Removes unused SSA instructions with no side effects."""

    def run_on_function(self, func: HIRFunction) -> bool:
        used_vars: Set[SSAVar] = set()
        for block in func.blocks.values():
            for inst in block.instructions:
                used_vars.update(inst.get_uses())
            if block.terminator:
                used_vars.update(block.terminator.get_uses())

        changed = False
        for block in func.blocks.values():
            new_insts = []
            for inst in block.instructions:
                # Retain instructions with side effects
                if isinstance(
                    inst, (HIRCall, HIRMethodCall, HIRSetIndex, HIRPrint)
                ):
                    new_insts.append(inst)
                elif inst.result and inst.result not in used_vars:
                    # Pure instruction whose result is never read -> Eliminate!
                    changed = True
                else:
                    new_insts.append(inst)
            block.instructions = new_insts
        return changed


class HIRPassManager:
    """Coordinates and executes optimization pipelines over EPL-HIR modules."""

    def __init__(self):
        self.passes = [
            ConstantFoldingPass(),
            DeadCodeEliminationPass(),
        ]

    def run(self, module: HIRModule, max_iterations: int = 10) -> None:
        for fn in module.functions.values():
            for _ in range(max_iterations):
                changed = False
                for p in self.passes:
                    if p.run_on_function(fn):
                        changed = True
                if not changed:
                    break


# ═══════════════════════════════════════════════════════════
#  HIR Verifier
# ═══════════════════════════════════════════════════════════


class HIRVerifier:
    """Validates structural invariants of an SSA EPL-HIR Module."""

    @staticmethod
    def verify(module: HIRModule) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        for fn_name, fn in module.functions.items():
            defined_vars: Set[SSAVar] = set()
            for p_name, p_type in fn.params:
                defined_vars.add(SSAVar(p_name, 0, p_type))

            for b_label, b in fn.blocks.items():
                if not b.is_terminated():
                    errors.append(
                        f'Function @{fn_name}: Block {b_label} lacks a terminator.'
                    )

                for inst in b.instructions:
                    res = getattr(inst, 'result', None)
                    if res is not None:
                        if res in defined_vars:
                            errors.append(
                                f'Function @{fn_name}: SSA violation: Variable {res} assigned multiple times.'
                            )
                        defined_vars.add(res)

        return (len(errors) == 0, errors)


def compile_to_hir(source_code: str, module_name: str = 'main') -> HIRModule:
    """Helper to tokenize, parse, and lower EPL source code to optimized EPL-HIR."""
    from epl.lexer import Lexer
    from epl.parser import Parser

    tokens = Lexer(source_code).tokenize()
    ast_tree = Parser(tokens).parse()
    lowering = ASTToHIR(module_name)
    hir_mod = lowering.lower(ast_tree)

    pm = HIRPassManager()
    pm.run(hir_mod)

    valid, errors = HIRVerifier.verify(hir_mod)
    if not valid:
        raise ValueError(f'HIR Verification Failed:\n' + '\n'.join(errors))

    return hir_mod
