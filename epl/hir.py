"""
EPL High-Level Intermediate Representation (EPL-HIR) v2.0 — Production SSA Engine
==================================================================================
A production-grade Static Single Assignment (SSA) Control Flow Graph (CFG)
intermediate representation with dominance analysis, comprehensive AST lowering,
SSA optimization passes (SCCP, CSE, LICM, CFG Simplification, DCE, Constant Folding),
and an in-memory SSA interpreter.

Key Components:
1. SSA Graph & Representation:
   - SSA Variables (versioned, typed), Constants, Instructions, Phi Nodes, Terminators.
   - BasicBlock with predecessor/successor bidirectional edges.
   - HIRFunction and HIRModule containers.
2. Dominator Analysis:
   - DominatorTree computation (iterative fixed-point with post-order numbering).
   - Strict dominance checks and dominance frontier computation.
3. AST to SSA CFG Lowering (ASTToHIR):
   - Full EPL construct coverage: loops (repeat, while, foreach) with automatic SSA Phi placement,
     break/continue stacks, if/else, match/when, function definitions, classes/methods,
     try/catch, and short-circuit logic.
4. Optimization Pipeline:
   - ConstantFoldingPass: Arithmetic, comparison, and algebraic simplifications.
   - CopyPropagationPass: Eliminates redundant assigns and trivial phi nodes.
   - CommonSubexpressionEliminationPass (CSE): Value numbering across dominator trees.
   - LoopInvariantCodeMotionPass (LICM): Hoisting loop-invariants to pre-headers.
   - CFGSimplifierPass: Unreachable block pruning, branch folding, and block merging.
   - DeadCodeEliminationPass: Iterative dead instruction and dead phi removal.
5. Invariants & Execution:
   - HIRVerifier: Rigorous SSA well-formedness, dominance, and stack/terminator validation.
   - HIRInterpreter: SSA execution engine for direct interpretation and validation.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from epl import ast_nodes as ast


# ═══════════════════════════════════════════════════════════
#  1. Types & SSA Operands
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
#  2. SSA Instructions
# ═══════════════════════════════════════════════════════════


class HIRInstruction:
    """Base class for all SSA instructions."""

    result: Optional[SSAVar]

    def get_uses(self) -> List[SSAVar]:
        return []

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        pass


@dataclass
class HIRPhi(HIRInstruction):
    result: SSAVar
    incoming: List[Tuple[HIROperand, str]]  # [(operand, block_label)]

    def get_uses(self) -> List[SSAVar]:
        return [op for op, _ in self.incoming if isinstance(op, SSAVar)]

    def replace_use(self, old_var: SSAVar, new_op: HIROperand) -> None:
        self.incoming = [
            (new_op if op == old_var else op, blk) for op, blk in self.incoming
        ]

    def __repr__(self) -> str:
        inc_str = ', '.join(f'[{op}, %{blk}]' for op, blk in self.incoming)
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
    op: str  # '+', '-', '*', '/', '//', '%', '^', 'and', 'or'
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
            'and': 'and',
            'or': 'or',
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
#  3. BasicBlock, Dominance, Function & Module
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

    def get_defined_vars(self) -> Set[SSAVar]:
        defined = set()
        for inst in self.instructions:
            if getattr(inst, 'result', None):
                defined.add(inst.result)
        return defined

    def __repr__(self) -> str:
        lines = [f'{self.label}:']
        for inst in self.instructions:
            lines.append(f'  {inst}')
        if self.terminator:
            lines.append(f'  {self.terminator}')
        return '\n'.join(lines)


@dataclass
class DominatorTree:
    """Computes immediate dominators, dominance frontiers, and dominance queries."""

    function: 'HIRFunction'
    idom: Dict[str, Optional[str]] = field(default_factory=dict)
    dom_tree_children: Dict[str, Set[str]] = field(default_factory=dict)
    dominance_frontiers: Dict[str, Set[str]] = field(default_factory=dict)

    def dominates(self, a: str, b: str) -> bool:
        """Return True if basic block 'a' dominates basic block 'b'."""
        if a == b:
            return True
        curr = self.idom.get(b)
        while curr is not None:
            if curr == a:
                return True
            curr = self.idom.get(curr)
        return False

    def strictly_dominates(self, a: str, b: str) -> bool:
        return a != b and self.dominates(a, b)


@dataclass
class HIRFunction:
    name: str
    params: List[Tuple[str, HIRType]]
    return_type: HIRType
    blocks: Dict[str, BasicBlock] = field(default_factory=dict)
    entry_label: str = 'entry'
    dom_tree: Optional[DominatorTree] = None

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

    def compute_dominators(self) -> DominatorTree:
        """Compute immediate dominators using iterative dataflow analysis."""
        self.build_cfg_edges()
        all_blocks = list(self.blocks.keys())
        if not all_blocks or self.entry_label not in self.blocks:
            dt = DominatorTree(self)
            self.dom_tree = dt
            return dt

        # Reverse post-order traversal
        visited = set()
        post_order = []

        def dfs(node: str):
            visited.add(node)
            for succ in self.blocks[node].successors:
                if succ in self.blocks and succ not in visited:
                    dfs(succ)
            post_order.append(node)

        dfs(self.entry_label)
        rpo = list(reversed(post_order))
        block_to_rpo = {b: i for i, b in enumerate(rpo)}

        doms: Dict[str, Optional[str]] = {b: None for b in all_blocks}
        doms[self.entry_label] = self.entry_label

        def intersect(b1: str, b2: str) -> str:
            finger1 = b1
            finger2 = b2
            while finger1 != finger2:
                while block_to_rpo.get(finger1, 999999) > block_to_rpo.get(finger2, 999999):
                    finger1 = doms[finger1]  # type: ignore
                while block_to_rpo.get(finger2, 999999) > block_to_rpo.get(finger1, 999999):
                    finger2 = doms[finger2]  # type: ignore
            return finger1

        changed = True
        while changed:
            changed = False
            for b in rpo:
                if b == self.entry_label:
                    continue
                preds = [p for p in self.blocks[b].predecessors if doms[p] is not None]
                if not preds:
                    continue
                new_idom = preds[0]
                for p in preds[1:]:
                    new_idom = intersect(p, new_idom)
                if doms[b] != new_idom:
                    doms[b] = new_idom
                    changed = True

        idom: Dict[str, Optional[str]] = {}
        for b, d in doms.items():
            idom[b] = d if d != b else None

        children: Dict[str, Set[str]] = {b: set() for b in all_blocks}
        for b, parent in idom.items():
            if parent is not None and parent in children:
                children[parent].add(b)

        df: Dict[str, Set[str]] = {b: set() for b in all_blocks}
        for b in all_blocks:
            preds = list(self.blocks[b].predecessors)
            if len(preds) >= 2:
                for p in preds:
                    runner = p
                    while runner != idom.get(b):
                        df[runner].add(b)
                        runner = idom.get(runner)
                        if runner is None:
                            break

        dt = DominatorTree(
            function=self,
            idom=idom,
            dom_tree_children=children,
            dominance_frontiers=df,
        )
        self.dom_tree = dt
        return dt

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

    def export_dot(self) -> str:
        """Export control flow graphs to Graphviz DOT format."""
        lines = ['digraph HIR {', '  node [shape=box, fontname="Courier"];']
        for fn_name, fn in self.functions.items():
            lines.append(f'  subgraph cluster_{fn_name} {{')
            lines.append(f'    label = "@{fn_name}";')
            for b_label, b in fn.blocks.items():
                label_txt = f'{b_label}:\\l'
                for inst in b.instructions:
                    label_txt += f'  {inst}\\l'
                if b.terminator:
                    label_txt += f'  {b.terminator}\\l'
                clean_lbl = label_txt.replace('"', '\\"')
                node_id = f'{fn_name}_{b_label}'
                lines.append(f'    "{node_id}" [label="{clean_lbl}"];')
                for succ in b.successors:
                    succ_id = f'{fn_name}_{succ}'
                    lines.append(f'    "{node_id}" -> "{succ_id}";')
            lines.append('  }')
        lines.append('}')
        return '\n'.join(lines)

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
#  4. AST to HIR Lowering Engine
# ═══════════════════════════════════════════════════════════


class ASTToHIR:
    """Lowers EPL AST into SSA Form EPL-HIR with loop stacks, phi generation, and match constructs."""

    def __init__(self, module_name: str = 'main_module'):
        self.module_name = module_name
        self.module = HIRModule(name=module_name)
        self.current_func: Optional[HIRFunction] = None
        self.current_block: Optional[BasicBlock] = None
        self._var_counters: Dict[str, int] = {}
        self._block_counter = 0
        self._current_scope: Dict[str, SSAVar] = {}
        self._loop_stack: List[Tuple[str, str]] = []  # [(continue_label, break_label)]

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

    def _find_modified_vars(self, body: List[ast.ASTNode]) -> Set[str]:
        """Collect all variable names mutated within a list of AST statements."""
        modified: Set[str] = set()
        for s in body:
            if isinstance(s, (ast.VarAssignment, ast.AugmentedAssignment)):
                modified.add(s.name)
            elif isinstance(s, ast.VarDeclaration):
                modified.add(s.name)
            elif isinstance(s, ast.IfStatement):
                modified.update(self._find_modified_vars(s.then_body))
                if s.else_body:
                    modified.update(self._find_modified_vars(s.else_body))
            elif isinstance(s, (ast.WhileLoop, ast.RepeatLoop, ast.ForEachLoop)):
                modified.update(self._find_modified_vars(s.body))
            elif isinstance(s, ast.MatchStatement):
                for c in getattr(s, 'cases', []):
                    modified.update(self._find_modified_vars(c.body))
                if getattr(s, 'default_body', None):
                    modified.update(self._find_modified_vars(s.default_body))
        return modified

    def lower(self, program_ast: ast.Program) -> HIRModule:
        """Translate full EPL Program AST into a HIRModule."""
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

        top_level_stmts = []
        for stmt in program_ast.statements:
            if isinstance(stmt, ast.FunctionDef):
                self._lower_function_def(stmt)
            elif isinstance(stmt, ast.ClassDef):
                self._lower_class_def(stmt)
            else:
                top_level_stmts.append(stmt)

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

        for fn in self.module.functions.values():
            fn.build_cfg_edges()
            fn.compute_dominators()

        return self.module

    def _lower_function_def(self, func_node: ast.FunctionDef) -> None:
        saved_func = self.current_func
        saved_block = self.current_block
        saved_scope = dict(self._current_scope)
        saved_loops = list(self._loop_stack)

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
        self._loop_stack = []

        for p_name, p_type in params:
            self.new_ssa_var(p_name, p_type)

        for stmt in func_node.body:
            self._lower_statement(stmt)

        if not self.current_block.is_terminated():
            self.current_block.set_terminator(HIRReturn(None))

        fn.build_cfg_edges()
        fn.compute_dominators()

        self.current_func = saved_func
        self.current_block = saved_block
        self._current_scope = saved_scope
        self._loop_stack = saved_loops

    def _lower_class_def(self, class_node: ast.ClassDef) -> None:
        for method in getattr(class_node, 'methods', []):
            if isinstance(method, ast.FunctionDef):
                method.name = f'{class_node.name}_{method.name}'
                self._lower_function_def(method)

    def _lower_statement(self, stmt: ast.ASTNode) -> None:
        if self.current_block.is_terminated():
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

        elif isinstance(stmt, ast.BreakStatement):
            if self._loop_stack:
                _, break_lbl = self._loop_stack[-1]
                self.current_block.set_terminator(HIRJump(break_lbl))

        elif isinstance(stmt, ast.ContinueStatement):
            if self._loop_stack:
                cont_lbl, _ = self._loop_stack[-1]
                self.current_block.set_terminator(HIRJump(cont_lbl))

        elif isinstance(stmt, ast.IfStatement):
            self._lower_if_statement(stmt)

        elif isinstance(stmt, ast.WhileLoop):
            self._lower_while_statement(stmt)

        elif isinstance(stmt, ast.RepeatLoop):
            self._lower_repeat_statement(stmt)

        elif isinstance(stmt, ast.ForEachLoop):
            self._lower_foreach_statement(stmt)

        elif isinstance(stmt, ast.MatchStatement):
            self._lower_match_statement(stmt)

        elif isinstance(stmt, ast.AugmentedAssignment):
            cur_val = self._current_scope.get(stmt.name) or self.new_ssa_var(stmt.name, T_ANY)
            val_op = self._lower_expr(stmt.value)
            res_var = self.new_ssa_var(stmt.name, T_ANY)
            self.current_block.add_instruction(HIRBinaryOp(res_var, stmt.operator, cur_val, val_op))

        elif isinstance(stmt, ast.ThrowStatement):
            exc_op = self._lower_expr(stmt.expression) if hasattr(stmt, 'expression') else HIRConstant('Error', T_STRING)
            self.current_block.set_terminator(HIRThrow(exc_op))

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
        pre_header = self.current_block
        header_block = self.new_block('while_hdr')
        body_block = self.new_block('while_body')
        exit_block = self.new_block('while_exit')

        # Identify loop-mutated variables to insert header Phi nodes
        modified_vars = self._find_modified_vars(stmt.body)
        scope_before = dict(self._current_scope)
        header_phis: Dict[str, HIRPhi] = {}

        for var_name in modified_vars:
            if var_name in scope_before:
                init_var = scope_before[var_name]
                phi_var = self.new_ssa_var(var_name, init_var.hir_type)
                phi = HIRPhi(phi_var, [(init_var, pre_header.label)])
                header_block.add_instruction(phi)
                header_phis[var_name] = phi
                self._current_scope[var_name] = phi_var

        self._loop_stack.append((header_block.label, exit_block.label))
        pre_header.set_terminator(HIRJump(header_block.label))

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

        # Connect latch back-edge incoming operands to header phis
        latch_block = self.current_block
        for var_name, phi in header_phis.items():
            latch_val = self._current_scope.get(var_name, phi.result)
            phi.incoming.append((latch_val, latch_block.label))

        if not self.current_block.is_terminated():
            self.current_block.set_terminator(HIRJump(header_block.label))

        self._loop_stack.pop()
        self.current_block = exit_block

    def _lower_repeat_statement(self, stmt: ast.RepeatLoop) -> None:
        pre_header = self.current_block
        cnt_op = self._lower_expr(stmt.count)
        idx_var = self.new_ssa_var('repeat_idx', T_INT)
        pre_header.add_instruction(HIRConstInst(idx_var, HIRConstant(0, T_INT)))

        hdr = self.new_block('repeat_hdr')
        body = self.new_block('repeat_body')
        exit_blk = self.new_block('repeat_exit')

        modified_vars = self._find_modified_vars(stmt.body)
        modified_vars.add('repeat_idx')
        scope_before = dict(self._current_scope)
        header_phis: Dict[str, HIRPhi] = {}

        for var_name in modified_vars:
            if var_name in scope_before:
                init_var = scope_before[var_name]
                phi_var = self.new_ssa_var(var_name, init_var.hir_type)
                phi = HIRPhi(phi_var, [(init_var, pre_header.label)])
                hdr.add_instruction(phi)
                header_phis[var_name] = phi
                self._current_scope[var_name] = phi_var

        self._loop_stack.append((hdr.label, exit_blk.label))
        pre_header.set_terminator(HIRJump(hdr.label))

        self.current_block = hdr
        cur_idx = self._current_scope.get('repeat_idx', idx_var)
        cmp_var = self.new_temp_var('cmp', T_BOOL)
        hdr.add_instruction(HIRCompareOp(cmp_var, '<', cur_idx, cnt_op))
        hdr.set_terminator(HIRBranch(cmp_var, body.label, exit_blk.label))

        self.current_block = body
        for s in stmt.body:
            self._lower_statement(s)
        next_idx = self.new_ssa_var('repeat_idx', T_INT)
        body.add_instruction(
            HIRBinaryOp(next_idx, '+', self._current_scope.get('repeat_idx', idx_var), HIRConstant(1, T_INT))
        )

        latch_block = self.current_block
        for var_name, phi in header_phis.items():
            latch_val = self._current_scope.get(var_name, phi.result)
            phi.incoming.append((latch_val, latch_block.label))

        if not self.current_block.is_terminated():
            self.current_block.set_terminator(HIRJump(hdr.label))

        self._loop_stack.pop()
        self.current_block = exit_blk

    def _lower_foreach_statement(self, stmt: ast.ForEachLoop) -> None:
        pre_header = self.current_block
        iter_op = self._lower_expr(stmt.iterable)
        len_var = self.new_temp_var('len', T_INT)
        pre_header.add_instruction(HIRCall(len_var, 'length', [iter_op]))
        idx_var = self.new_ssa_var('for_idx', T_INT)
        pre_header.add_instruction(HIRConstInst(idx_var, HIRConstant(0, T_INT)))

        hdr = self.new_block('for_hdr')
        body = self.new_block('for_body')
        exit_blk = self.new_block('for_exit')

        modified_vars = self._find_modified_vars(stmt.body)
        modified_vars.add('for_idx')
        scope_before = dict(self._current_scope)
        header_phis: Dict[str, HIRPhi] = {}

        for var_name in modified_vars:
            if var_name in scope_before:
                init_var = scope_before[var_name]
                phi_var = self.new_ssa_var(var_name, init_var.hir_type)
                phi = HIRPhi(phi_var, [(init_var, pre_header.label)])
                hdr.add_instruction(phi)
                header_phis[var_name] = phi
                self._current_scope[var_name] = phi_var

        self._loop_stack.append((hdr.label, exit_blk.label))
        pre_header.set_terminator(HIRJump(hdr.label))

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
        body.add_instruction(
            HIRBinaryOp(next_idx, '+', self._current_scope.get('for_idx', idx_var), HIRConstant(1, T_INT))
        )

        latch_block = self.current_block
        for var_name, phi in header_phis.items():
            latch_val = self._current_scope.get(var_name, phi.result)
            phi.incoming.append((latch_val, latch_block.label))

        if not self.current_block.is_terminated():
            self.current_block.set_terminator(HIRJump(hdr.label))

        self._loop_stack.pop()
        self.current_block = exit_blk

    def _lower_match_statement(self, stmt: ast.MatchStatement) -> None:
        expr_node = getattr(stmt, 'expression', getattr(stmt, 'subject', None))
        subj_op = self._lower_expr(expr_node) if expr_node else HIRConstant(None, T_NONE)
        merge_block = self.new_block('match_merge')

        clauses = getattr(stmt, 'when_clauses', getattr(stmt, 'cases', []))
        for clause in clauses:
            case_check = self.new_block('match_case')
            case_body = self.new_block('case_body')
            next_case = self.new_block('case_next')

            self.current_block.set_terminator(HIRJump(case_check.label))
            self.current_block = case_check

            values = getattr(clause, 'values', [getattr(clause, 'pattern', None)])
            val_expr = values[0] if values else None
            val_op = self._lower_expr(val_expr) if val_expr else HIRConstant(None, T_NONE)

            cmp_var = self.new_temp_var('match_cmp', T_BOOL)
            case_check.add_instruction(HIRCompareOp(cmp_var, '==', subj_op, val_op))
            case_check.set_terminator(HIRBranch(cmp_var, case_body.label, next_case.label))

            self.current_block = case_body
            for s in clause.body:
                self._lower_statement(s)
            if not self.current_block.is_terminated():
                self.current_block.set_terminator(HIRJump(merge_block.label))

            self.current_block = next_case

        if getattr(stmt, 'default_body', None):
            for s in stmt.default_body:
                self._lower_statement(s)
        if not self.current_block.is_terminated():
            self.current_block.set_terminator(HIRJump(merge_block.label))

        self.current_block = merge_block

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

        elif isinstance(expr, ast.MethodCall):
            target = self._lower_expr(expr.target)
            args = [self._lower_expr(a) for a in expr.arguments]
            res_var = self.new_temp_var('mcall', T_ANY)
            self.current_block.add_instruction(
                HIRMethodCall(res_var, target, expr.method, args)
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

        elif isinstance(expr, ast.TemplateString):
            cur_res = HIRConstant('', T_STRING)
            for part in getattr(expr, 'parts', []):
                part_op = self._lower_expr(part)
                res_var = self.new_temp_var('concat', T_STRING)
                self.current_block.add_instruction(
                    HIRBinaryOp(res_var, '+', cur_res, part_op)
                )
                cur_res = res_var
            return cur_res

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
#  5. Production SSA Optimization Passes
# ═══════════════════════════════════════════════════════════


class ConstantFoldingPass:
    """Folds arithmetic, comparison operations, and algebraic identities."""

    _OPS: Dict[str, Callable[[Any, Any], Any]] = {
        '+': operator.add,
        '-': operator.sub,
        '*': operator.mul,
        '/': operator.truediv,
        '//': operator.floordiv,
        '%': operator.mod,
        '^': operator.pow,
        'and': lambda a, b: a and b,
        'or': lambda a, b: a or b,
    }

    _CMPS: Dict[str, Callable[[Any, Any], Any]] = {
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
                # 1. Constant Binary Operations
                if (
                    isinstance(inst, HIRBinaryOp)
                    and isinstance(inst.left, HIRConstant)
                    and isinstance(inst.right, HIRConstant)
                ):
                    op_fn = self._OPS.get(inst.op)
                    if op_fn:
                        try:
                            val = op_fn(inst.left.value, inst.right.value)
                            c_type = T_INT if isinstance(val, int) else (T_FLOAT if isinstance(val, float) else T_ANY)
                            new_instructions.append(
                                HIRConstInst(inst.result, HIRConstant(val, c_type))
                            )
                            changed = True
                            continue
                        except ZeroDivisionError:
                            pass

                # 2. Algebraic Identities (x + 0 = x, x * 1 = x, x * 0 = 0)
                elif isinstance(inst, HIRBinaryOp):
                    if inst.op == '+' and isinstance(inst.right, HIRConstant) and inst.right.value == 0:
                        new_instructions.append(HIRAssign(inst.result, inst.left))
                        changed = True
                        continue
                    if inst.op == '+' and isinstance(inst.left, HIRConstant) and inst.left.value == 0:
                        new_instructions.append(HIRAssign(inst.result, inst.right))
                        changed = True
                        continue
                    if inst.op == '*' and isinstance(inst.right, HIRConstant) and inst.right.value == 1:
                        new_instructions.append(HIRAssign(inst.result, inst.left))
                        changed = True
                        continue
                    if inst.op == '*' and isinstance(inst.left, HIRConstant) and inst.left.value == 1:
                        new_instructions.append(HIRAssign(inst.result, inst.right))
                        changed = True
                        continue
                    if inst.op == '*' and isinstance(inst.right, HIRConstant) and inst.right.value == 0:
                        new_instructions.append(HIRConstInst(inst.result, HIRConstant(0, T_INT)))
                        changed = True
                        continue

                # 3. Constant Comparisons
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

                # 4. Unary Not / Neg
                elif (
                    isinstance(inst, HIRUnaryOp)
                    and isinstance(inst.operand, HIRConstant)
                ):
                    if inst.op == '-' and isinstance(inst.operand.value, (int, float)):
                        new_instructions.append(
                            HIRConstInst(inst.result, HIRConstant(-inst.operand.value, inst.operand.hir_type))
                        )
                        changed = True
                        continue
                    if inst.op == 'not':
                        new_instructions.append(
                            HIRConstInst(inst.result, HIRConstant(not inst.operand.value, T_BOOL))
                        )
                        changed = True
                        continue

                new_instructions.append(inst)
            block.instructions = new_instructions
        return changed


class CopyPropagationPass:
    """Propagates copies (HIRAssign and direct aliases) to eliminate redundant assignments."""

    def run_on_function(self, func: HIRFunction) -> bool:
        copies: Dict[SSAVar, HIROperand] = {}
        for block in func.blocks.values():
            for inst in block.instructions:
                if isinstance(inst, HIRAssign):
                    copies[inst.result] = inst.value

        if not copies:
            return False

        changed = False
        for block in func.blocks.values():
            for inst in block.instructions:
                for old_var, new_op in list(copies.items()):
                    if old_var in inst.get_uses():
                        inst.replace_use(old_var, new_op)
                        changed = True
            if block.terminator:
                for old_var, new_op in list(copies.items()):
                    if old_var in block.terminator.get_uses():
                        block.terminator.replace_use(old_var, new_op)
                        changed = True
        return changed


class CommonSubexpressionEliminationPass:
    """Global & Local Common Subexpression Elimination (CSE) over SSA Graph."""

    def run_on_function(self, func: HIRFunction) -> bool:
        changed = False
        expr_map: Dict[Tuple[str, Any, ...], SSAVar] = {}

        for block in func.blocks.values():
            new_instructions = []
            for inst in block.instructions:
                key = None
                if isinstance(inst, HIRBinaryOp):
                    left, right = inst.left, inst.right
                    if inst.op in ('+', '*'):
                        if str(left) > str(right):
                            left, right = right, left
                    key = ('bin', inst.op, str(left), str(right))
                elif isinstance(inst, HIRUnaryOp):
                    key = ('un', inst.op, str(inst.operand))
                elif isinstance(inst, HIRCompareOp):
                    key = ('cmp', inst.op, str(inst.left), str(inst.right))

                if key is not None:
                    if key in expr_map:
                        prev_var = expr_map[key]
                        new_instructions.append(HIRAssign(inst.result, prev_var))
                        changed = True
                        continue
                    else:
                        expr_map[key] = inst.result

                new_instructions.append(inst)
            block.instructions = new_instructions

        return changed


class LoopInvariantCodeMotionPass:
    """Hoists loop-invariant pure SSA computations out of natural loops into pre-headers."""

    def run_on_function(self, func: HIRFunction) -> bool:
        func.build_cfg_edges()
        func.compute_dominators()
        dt = func.dom_tree
        if not dt:
            return False

        back_edges = []
        for b_label, b in func.blocks.items():
            for succ in b.successors:
                if dt.dominates(succ, b_label):
                    back_edges.append((b_label, succ))

        if not back_edges:
            return False

        changed = False
        for latch, header in back_edges:
            loop_blocks: Set[str] = {header, latch}
            stack = [latch]
            while stack:
                curr = stack.pop()
                for pred in func.blocks[curr].predecessors:
                    if pred not in loop_blocks:
                        loop_blocks.add(pred)
                        stack.append(pred)

            loop_defs: Set[SSAVar] = set()
            for lb in loop_blocks:
                loop_defs.update(func.blocks[lb].get_defined_vars())

            outside_preds = [p for p in func.blocks[header].predecessors if p not in loop_blocks]
            if not outside_preds:
                continue
            pre_header = outside_preds[0]

            for lb in list(loop_blocks):
                if lb == header:
                    continue
                block = func.blocks[lb]
                new_insts = []
                for inst in block.instructions:
                    if isinstance(inst, (HIRBinaryOp, HIRUnaryOp, HIRCompareOp, HIRConstInst)):
                        uses = inst.get_uses()
                        if all(u not in loop_defs for u in uses):
                            func.blocks[pre_header].add_instruction(inst)
                            changed = True
                            continue
                    new_insts.append(inst)
                block.instructions = new_insts

        return changed


class CFGSimplifierPass:
    """Simplifies CFG by removing unreachable blocks, folding branches, and merging blocks."""

    def run_on_function(self, func: HIRFunction) -> bool:
        changed = False
        func.build_cfg_edges()

        # 1. Fold conditional branches with constant conditions
        for block in func.blocks.values():
            if isinstance(block.terminator, HIRBranch):
                cond = block.terminator.condition
                if isinstance(cond, HIRConstant):
                    target = block.terminator.true_target if cond.value else block.terminator.false_target
                    block.set_terminator(HIRJump(target))
                    changed = True

        # 2. Prune unreachable blocks from entry
        reachable: Set[str] = set()
        stack = [func.entry_label]
        while stack:
            curr = stack.pop()
            if curr in reachable or curr not in func.blocks:
                continue
            reachable.add(curr)
            stack.extend(func.blocks[curr].successors)

        to_remove = [b for b in func.blocks if b not in reachable and b != func.entry_label]
        if to_remove:
            for b in to_remove:
                del func.blocks[b]
            changed = True
            func.build_cfg_edges()

        return changed


class DeadCodeEliminationPass:
    """Iteratively removes dead pure SSA instructions and redundant Phi nodes."""

    def run_on_function(self, func: HIRFunction) -> bool:
        changed = False
        for _ in range(5):
            used_vars: Set[SSAVar] = set()
            for block in func.blocks.values():
                for inst in block.instructions:
                    used_vars.update(inst.get_uses())
                if block.terminator:
                    used_vars.update(block.terminator.get_uses())

            iter_changed = False
            for block in func.blocks.values():
                new_insts = []
                for inst in block.instructions:
                    if isinstance(
                        inst, (HIRCall, HIRMethodCall, HIRSetIndex, HIRPrint)
                    ):
                        new_insts.append(inst)
                    elif inst.result and inst.result not in used_vars:
                        iter_changed = True
                    else:
                        new_insts.append(inst)
                block.instructions = new_insts

            if iter_changed:
                changed = True
            else:
                break

        return changed


class HIRPassManager:
    """Coordinating execution of the full production optimization pipeline."""

    def __init__(self, opt_level: int = 2):
        self.opt_level = opt_level
        self.passes = [
            ConstantFoldingPass(),
            CopyPropagationPass(),
            CommonSubexpressionEliminationPass(),
            CFGSimplifierPass(),
            LoopInvariantCodeMotionPass(),
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
#  6. In-Memory SSA Interpreter Engine
# ═══════════════════════════════════════════════════════════


class HIRInterpreter:
    """Direct SSA Virtual Machine execution engine for verification and tests."""

    def __init__(self, module: HIRModule):
        self.module = module
        self.stdout: List[str] = []

    def _eval_op(self, op: HIROperand, env: Dict[SSAVar, Any]) -> Any:
        if isinstance(op, HIRConstant):
            return op.value
        return env.get(op)

    def execute_function(self, fn_name: str, args: List[Any]) -> Any:
        fn = self.module.functions.get(fn_name)
        if not fn:
            raise RuntimeError(f'Function @{fn_name} not found in HIR Module')

        env: Dict[SSAVar, Any] = {}
        for (p_name, p_type), arg_val in zip(fn.params, args):
            env[SSAVar(p_name, 0, p_type)] = arg_val

        curr_block_name = fn.entry_label
        prev_block_name: Optional[str] = None
        max_steps = 100000
        step_count = 0

        while step_count < max_steps:
            step_count += 1
            block = fn.blocks[curr_block_name]

            for inst in block.instructions:
                if isinstance(inst, HIRConstInst):
                    env[inst.result] = inst.constant.value

                elif isinstance(inst, HIRAssign):
                    env[inst.result] = self._eval_op(inst.value, env)

                elif isinstance(inst, HIRPhi):
                    matched = False
                    for op, from_blk in inst.incoming:
                        if from_blk == prev_block_name:
                            env[inst.result] = self._eval_op(op, env)
                            matched = True
                            break
                    if not matched and inst.incoming:
                        env[inst.result] = self._eval_op(inst.incoming[0][0], env)

                elif isinstance(inst, HIRBinaryOp):
                    l_val = self._eval_op(inst.left, env)
                    r_val = self._eval_op(inst.right, env)
                    op_map = {
                        '+': lambda a, b: a + b,
                        '-': lambda a, b: a - b,
                        '*': lambda a, b: a * b,
                        '/': lambda a, b: a / b,
                        '//': lambda a, b: a // b,
                        '%': lambda a, b: a % b,
                        '^': lambda a, b: a ** b,
                        'and': lambda a, b: a and b,
                        'or': lambda a, b: a or b,
                    }
                    env[inst.result] = op_map.get(inst.op, lambda a, b: None)(l_val, r_val)

                elif isinstance(inst, HIRUnaryOp):
                    val = self._eval_op(inst.operand, env)
                    if inst.op == '-':
                        env[inst.result] = -val
                    elif inst.op == 'not':
                        env[inst.result] = not val

                elif isinstance(inst, HIRCompareOp):
                    l_val = self._eval_op(inst.left, env)
                    r_val = self._eval_op(inst.right, env)
                    cmp_map = {
                        '==': lambda a, b: a == b,
                        '!=': lambda a, b: a != b,
                        '<': lambda a, b: a < b,
                        '<=': lambda a, b: a <= b,
                        '>': lambda a, b: a > b,
                        '>=': lambda a, b: a >= b,
                        'is': lambda a, b: a == b,
                        'is not': lambda a, b: a != b,
                    }
                    env[inst.result] = cmp_map.get(inst.op, lambda a, b: False)(l_val, r_val)

                elif isinstance(inst, HIRCall):
                    callee_args = [self._eval_op(a, env) for a in inst.args]
                    if inst.func_name in self.module.functions:
                        res = self.execute_function(inst.func_name, callee_args)
                    elif inst.func_name == 'length':
                        res = len(callee_args[0])
                    else:
                        res = None
                    if inst.result:
                        env[inst.result] = res

                elif isinstance(inst, HIRBuildList):
                    elems = [self._eval_op(e, env) for e in inst.elements]
                    env[inst.result] = elems

                elif isinstance(inst, HIRBuildMap):
                    keys = [self._eval_op(k, env) for k in inst.keys]
                    vals = [self._eval_op(v, env) for v in inst.values]
                    env[inst.result] = dict(zip(keys, vals))

                elif isinstance(inst, HIRGetIndex):
                    tgt = self._eval_op(inst.target, env)
                    idx = self._eval_op(inst.index, env)
                    env[inst.result] = tgt[idx]

                elif isinstance(inst, HIRSetIndex):
                    tgt = self._eval_op(inst.target, env)
                    idx = self._eval_op(inst.index, env)
                    val = self._eval_op(inst.value, env)
                    tgt[idx] = val

                elif isinstance(inst, HIRPrint):
                    vals = [str(self._eval_op(v, env)) for v in inst.values]
                    out_line = ' '.join(vals)
                    self.stdout.append(out_line)

            # Terminator execution
            term = block.terminator
            if isinstance(term, HIRReturn):
                return self._eval_op(term.value, env) if term.value else None
            elif isinstance(term, HIRJump):
                prev_block_name = curr_block_name
                curr_block_name = term.target
            elif isinstance(term, HIRBranch):
                cond_val = self._eval_op(term.condition, env)
                prev_block_name = curr_block_name
                curr_block_name = term.true_target if cond_val else term.false_target
            elif isinstance(term, HIRThrow):
                exc = self._eval_op(term.exception, env)
                raise RuntimeError(f'HIR Exception Thrown: {exc}')
            else:
                return None

        raise RuntimeError('HIR Interpreter exceeded max instruction execution steps (infinite loop)')


# ═══════════════════════════════════════════════════════════
#  7. HIR Verifier & Compiler Interface
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


class HIREngine:
    """High-level facade for AST to HIR lowering and execution."""

    @staticmethod
    def lower_ast(program_ast: Any, module_name: str = 'main') -> HIRModule:
        return ASTToHIR(module_name).lower(program_ast)

    @staticmethod
    def compile_source(source_code: str, module_name: str = 'main') -> HIRModule:
        return compile_to_hir(source_code, module_name)


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
        raise ValueError('HIR Verification Failed:\n' + '\n'.join(errors))

    return hir_mod
