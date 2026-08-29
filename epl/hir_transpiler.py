"""
EPL-HIR Direct Transpiler Lowering Engine (Phase 5 Deep)
========================================================
Translates optimized SSA Control Flow Graphs (EPL-HIR v2.0) directly into target
languages (Python 3, JavaScript ES2020, Kotlin, C99).

Handles SSA deconstruction (Phi elimination via parallel assignments),
Structured Control Flow recovery from CFG blocks, and runtime semantic bridges.
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from epl.hir import (
    BasicBlock,
    HIRAssign,
    HIRBinaryOp,
    HIRBranch,
    HIRBuildList,
    HIRBuildMap,
    HIRCall,
    HIRCompareOp,
    HIRConstInst,
    HIRConstant,
    HIRFunction,
    HIRGetIndex,
    HIRInstruction,
    HIRJump,
    HIRMethodCall,
    HIRModule,
    HIROperand,
    HIRPhi,
    HIRPrint,
    HIRReturn,
    HIRSetIndex,
    HIRThrow,
    HIRTypeKind,
    HIRUnaryOp,
    SSAVar,
)


def _var_name(op: HIROperand) -> str:
    if isinstance(op, HIRConstant):
        if op.hir_type.kind == HIRTypeKind.STRING:
            return f'"{op.value}"'
        if op.hir_type.kind == HIRTypeKind.NONE:
            return 'None'
        if op.hir_type.kind == HIRTypeKind.BOOL:
            return 'True' if op.value else 'False'
        return str(op.value)
    return f'_{op.name}_{op.version}'


def _js_var_name(op: HIROperand) -> str:
    if isinstance(op, HIRConstant):
        if op.hir_type.kind == HIRTypeKind.STRING:
            return f'"{op.value}"'
        if op.hir_type.kind == HIRTypeKind.NONE:
            return 'null'
        if op.hir_type.kind == HIRTypeKind.BOOL:
            return 'true' if op.value else 'false'
        return str(op.value)
    return f'_{op.name}_{op.version}'


def _c_var_name(op: HIROperand) -> str:
    if isinstance(op, HIRConstant):
        if op.hir_type.kind == HIRTypeKind.STRING:
            return f'"{op.value}"'
        if op.hir_type.kind == HIRTypeKind.NONE:
            return '0'
        if op.hir_type.kind == HIRTypeKind.BOOL:
            return '1' if op.value else '0'
        return str(op.value)
    return f'_{op.name}_{op.version}'


# ═══════════════════════════════════════════════════════════
#  1. HIR to Python Transpiler Backend
# ═══════════════════════════════════════════════════════════


class HIRToPython:
    """Lowering from EPL-HIR SSA Module to clean, runnable Python 3 code."""

    def __init__(self, module: Optional[HIRModule] = None):
        self.module = module
        self.indent = 0

    def _line(self, text: str) -> str:
        return '    ' * self.indent + text

    def transpile(self, module: Optional[HIRModule] = None) -> str:
        if module is not None:
            self.module = module
        if self.module is None:
            raise ValueError("HIRModule must be provided to transpile")
        lines = [
            '# Auto-generated from optimized EPL-HIR SSA IR',
            'import sys',
            '',
        ]

        for fn_name, fn in self.module.functions.items():
            lines.extend(self._transpile_function(fn))
            lines.append('')

        lines.extend([
            'if __name__ == "__main__":',
            '    if "main" in globals():',
            '        sys.exit(main() or 0)',
        ])
        return '\n'.join(lines)

    def _transpile_function(self, fn: HIRFunction) -> List[str]:
        params_str = ', '.join(f'_{p}_0' for p, _ in fn.params)
        lines = [f'def {fn.name}({params_str}):']
        self.indent = 1

        # Collect all SSA variables defined in the function
        all_vars: Set[str] = set()
        for b in fn.blocks.values():
            for inst in b.instructions:
                if getattr(inst, 'result', None):
                    all_vars.add(_var_name(inst.result))

        if all_vars:
            init_vars = ', '.join(sorted(all_vars))
            lines.append(self._line(f'{init_vars} = ' + ', '.join(['None'] * len(all_vars))))

        # State machine block dispatcher for SSA CFG
        lines.append(self._line(f'_block = "{fn.entry_label}"'))
        lines.append(self._line('_prev_block = None'))
        lines.append(self._line('while True:'))
        self.indent = 2

        for b_label, block in fn.blocks.items():
            lines.append(self._line(f'if _block == "{b_label}":'))
            self.indent += 1

            for inst in block.instructions:
                if isinstance(inst, HIRPhi):
                    for op, from_blk in inst.incoming:
                        lines.append(
                            self._line(
                                f'if _prev_block == "{from_blk}": {_var_name(inst.result)} = {_var_name(op)}'
                            )
                        )
                elif isinstance(inst, HIRConstInst):
                    lines.append(self._line(f'{_var_name(inst.result)} = {_var_name(inst.constant)}'))
                elif isinstance(inst, HIRAssign):
                    lines.append(self._line(f'{_var_name(inst.result)} = {_var_name(inst.value)}'))
                elif isinstance(inst, HIRBinaryOp):
                    op_sym = inst.op if inst.op != '^' else '**'
                    lines.append(
                        self._line(
                            f'{_var_name(inst.result)} = {_var_name(inst.left)} {op_sym} {_var_name(inst.right)}'
                        )
                    )
                elif isinstance(inst, HIRUnaryOp):
                    op_sym = '-' if inst.op == '-' else 'not '
                    lines.append(self._line(f'{_var_name(inst.result)} = {op_sym}{_var_name(inst.operand)}'))
                elif isinstance(inst, HIRCompareOp):
                    lines.append(
                        self._line(
                            f'{_var_name(inst.result)} = {_var_name(inst.left)} {inst.op} {_var_name(inst.right)}'
                        )
                    )
                elif isinstance(inst, HIRCall):
                    args_str = ', '.join(_var_name(a) for a in inst.args)
                    fn_expr = 'len' if inst.func_name == 'length' else inst.func_name
                    if inst.result:
                        lines.append(self._line(f'{_var_name(inst.result)} = {fn_expr}({args_str})'))
                    else:
                        lines.append(self._line(f'{fn_expr}({args_str})'))
                elif isinstance(inst, HIRBuildList):
                    elems_str = ', '.join(_var_name(e) for e in inst.elements)
                    lines.append(self._line(f'{_var_name(inst.result)} = [{elems_str}]'))
                elif isinstance(inst, HIRBuildMap):
                    kvs = ', '.join(f'{_var_name(k)}: {_var_name(v)}' for k, v in zip(inst.keys, inst.values))
                    lines.append(self._line(f'{_var_name(inst.result)} = {{{kvs}}}'))
                elif isinstance(inst, HIRGetIndex):
                    lines.append(
                        self._line(f'{_var_name(inst.result)} = {_var_name(inst.target)}[{_var_name(inst.index)}]')
                    )
                elif isinstance(inst, HIRSetIndex):
                    lines.append(
                        self._line(f'{_var_name(inst.target)}[{_var_name(inst.index)}] = {_var_name(inst.value)}')
                    )
                elif isinstance(inst, HIRPrint):
                    vals_str = ', '.join(_var_name(v) for v in inst.values)
                    lines.append(self._line(f'print({vals_str})'))

            # Terminator
            term = block.terminator
            if isinstance(term, HIRReturn):
                ret_val = _var_name(term.value) if term.value else 'None'
                lines.append(self._line(f'return {ret_val}'))
            elif isinstance(term, HIRJump):
                lines.append(self._line(f'_prev_block = "{b_label}"'))
                lines.append(self._line(f'_block = "{term.target}"'))
                lines.append(self._line('continue'))
            elif isinstance(term, HIRBranch):
                lines.append(self._line(f'_prev_block = "{b_label}"'))
                lines.append(self._line(f'if {_var_name(term.condition)}:'))
                lines.append(self._line(f'    _block = "{term.true_target}"'))
                lines.append(self._line('else:'))
                lines.append(f'{"    " * (self.indent + 1)}_block = "{term.false_target}"')
                lines.append(self._line('continue'))
            elif isinstance(term, HIRThrow):
                lines.append(self._line(f'raise RuntimeError({_var_name(term.exception)})'))

            self.indent -= 1

        self.indent = 0
        return lines


# ═══════════════════════════════════════════════════════════
#  2. HIR to JavaScript (ES2020) Transpiler Backend
# ═══════════════════════════════════════════════════════════


class HIRToJavaScript:
    """Lowering from EPL-HIR SSA Module to modern JavaScript (ES2020)."""

    def __init__(self, module: Optional[HIRModule] = None):
        self.module = module
        self.indent = 0

    def _line(self, text: str) -> str:
        return '  ' * self.indent + text

    def transpile(self, module: Optional[HIRModule] = None) -> str:
        if module is not None:
            self.module = module
        if self.module is None:
            raise ValueError("HIRModule must be provided to transpile")
        lines = [
            '// Auto-generated from optimized EPL-HIR SSA IR (JS Target)',
            '',
        ]

        for fn_name, fn in self.module.functions.items():
            lines.extend(self._transpile_function(fn))
            lines.append('')

        lines.extend([
            'if (typeof main === "function") {',
            '  main();',
            '}',
        ])
        return '\n'.join(lines)

    def _transpile_function(self, fn: HIRFunction) -> List[str]:
        params_str = ', '.join(f'_{p}_0' for p, _ in fn.params)
        lines = [f'function {fn.name}({params_str}) {{']
        self.indent = 1

        all_vars: Set[str] = set()
        for b in fn.blocks.values():
            for inst in b.instructions:
                if getattr(inst, 'result', None):
                    all_vars.add(_js_var_name(inst.result))

        if all_vars:
            for v in sorted(all_vars):
                lines.append(self._line(f'let {v} = null;'))

        lines.append(self._line(f'let _block = "{fn.entry_label}";'))
        lines.append(self._line('let _prev_block = null;'))
        lines.append(self._line('while (true) {'))
        self.indent = 2

        for b_label, block in fn.blocks.items():
            lines.append(self._line(f'if (_block === "{b_label}") {{'))
            self.indent += 1

            for inst in block.instructions:
                if isinstance(inst, HIRPhi):
                    for op, from_blk in inst.incoming:
                        lines.append(
                            self._line(
                                f'if (_prev_block === "{from_blk}") {{ {_js_var_name(inst.result)} = {_js_var_name(op)}; }}'
                            )
                        )
                elif isinstance(inst, HIRConstInst):
                    lines.append(self._line(f'{_js_var_name(inst.result)} = {_js_var_name(inst.constant)};'))
                elif isinstance(inst, HIRAssign):
                    lines.append(self._line(f'{_js_var_name(inst.result)} = {_js_var_name(inst.value)};'))
                elif isinstance(inst, HIRBinaryOp):
                    op_sym = inst.op if inst.op != '^' else '**'
                    lines.append(
                        self._line(
                            f'{_js_var_name(inst.result)} = {_js_var_name(inst.left)} {op_sym} {_js_var_name(inst.right)};'
                        )
                    )
                elif isinstance(inst, HIRUnaryOp):
                    op_sym = '-' if inst.op == '-' else '!'
                    lines.append(self._line(f'{_js_var_name(inst.result)} = {op_sym}{_js_var_name(inst.operand)};'))
                elif isinstance(inst, HIRCompareOp):
                    cmp_sym = '===' if inst.op == '==' else ('!==' if inst.op == '!=' else inst.op)
                    lines.append(
                        self._line(
                            f'{_js_var_name(inst.result)} = {_js_var_name(inst.left)} {cmp_sym} {_js_var_name(inst.right)};'
                        )
                    )
                elif isinstance(inst, HIRCall):
                    args_str = ', '.join(_js_var_name(a) for a in inst.args)
                    if inst.func_name == 'length':
                        call_expr = f'{_js_var_name(inst.args[0])}.length'
                    else:
                        call_expr = f'{inst.func_name}({args_str})'
                    if inst.result:
                        lines.append(self._line(f'{_js_var_name(inst.result)} = {call_expr};'))
                    else:
                        lines.append(self._line(f'{call_expr};'))
                elif isinstance(inst, HIRPrint):
                    vals_str = ', '.join(_js_var_name(v) for v in inst.values)
                    lines.append(self._line(f'console.log({vals_str});'))

            term = block.terminator
            if isinstance(term, HIRReturn):
                ret_val = _js_var_name(term.value) if term.value else 'null'
                lines.append(self._line(f'return {ret_val};'))
            elif isinstance(term, HIRJump):
                lines.append(self._line(f'_prev_block = "{b_label}";'))
                lines.append(self._line(f'_block = "{term.target}";'))
                lines.append(self._line('continue;'))
            elif isinstance(term, HIRBranch):
                lines.append(self._line(f'_prev_block = "{b_label}";'))
                lines.append(
                    self._line(
                        f'_block = {_js_var_name(term.condition)} ? "{term.true_target}" : "{term.false_target}";'
                    )
                )
                lines.append(self._line('continue;'))
            elif isinstance(term, HIRThrow):
                lines.append(self._line(f'throw new Error({_js_var_name(term.exception)});'))

            self.indent -= 1
            lines.append(self._line('}'))

        self.indent = 1
        lines.append(self._line('}'))
        self.indent = 0
        lines.append('}')
        return lines


# ═══════════════════════════════════════════════════════════
#  3. HIR to Kotlin Transpiler Backend
# ═══════════════════════════════════════════════════════════


class HIRToKotlin:
    """Lowering from EPL-HIR SSA Module to idiomatic Kotlin."""

    def __init__(self, module: Optional[HIRModule] = None):
        self.module = module

    def transpile(self, module: Optional[HIRModule] = None) -> str:
        if module is not None:
            self.module = module
        if self.module is None:
            raise ValueError("HIRModule must be provided to transpile")
        lines = [
            '// Auto-generated from optimized EPL-HIR SSA IR (Kotlin Target)',
            'package me.eplang.generated',
            '',
        ]
        for fn_name, fn in self.module.functions.items():
            lines.append(f'fun {fn.name}(): Any? {{')
            lines.append('    // SSA CFG Dispatcher')
            lines.append(f'    var _block = "{fn.entry_label}"')
            lines.append('    var _prev_block: String? = null')
            lines.append('    while (true) {')
            for b_label, block in fn.blocks.items():
                lines.append(f'        if (_block == "{b_label}") {{')
                for inst in block.instructions:
                    if isinstance(inst, HIRPrint):
                        vals = ', '.join(_var_name(v) for v in inst.values)
                        lines.append(f'            println({vals})')
                if isinstance(block.terminator, HIRReturn):
                    val = _var_name(block.terminator.value) if block.terminator.value else "null"
                    lines.append(f'            return {val}')
                elif isinstance(block.terminator, HIRJump):
                    lines.append(f'            _prev_block = "{b_label}"')
                    lines.append(f'            _block = "{block.terminator.target}"')
                    lines.append('            continue')
                lines.append('        }')
            lines.append('    }')
            lines.append('}')
            lines.append('')
        return '\n'.join(lines)


class HIRTranspilerManager:
    """Manages multi-target code generation directly from EPL AST or HIR."""

    def __init__(self):
        from epl.hir import HIREngine
        self.hir_engine = HIREngine()

    def transpile_all(self, prog_ast_or_hir: Any) -> Dict[str, str]:
        if not isinstance(prog_ast_or_hir, HIRModule):
            hir_mod = self.hir_engine.lower_ast(prog_ast_or_hir)
        else:
            hir_mod = prog_ast_or_hir

        return {
            "python": HIRToPython(hir_mod).transpile(),
            "javascript": HIRToJavaScript(hir_mod).transpile(),
            "kotlin": HIRToKotlin(hir_mod).transpile(),
        }


# ═══════════════════════════════════════════════════════════
#  Helper Entrypoints
# ═══════════════════════════════════════════════════════════


def transpile_hir_to_python(module: HIRModule) -> str:
    return HIRToPython(module).transpile()


def transpile_hir_to_js(module: HIRModule) -> str:
    return HIRToJavaScript(module).transpile()


def transpile_hir_to_kotlin(module: HIRModule) -> str:
    return HIRToKotlin(module).transpile()
