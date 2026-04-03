"""Pytest smoke coverage for the llvmlite target-machine API used by EPL."""

import importlib.util

import pytest


HAS_LLVM = importlib.util.find_spec("llvmlite.binding") is not None
pytestmark = pytest.mark.skipif(not HAS_LLVM, reason="llvmlite is not installed")


def _llvm():
    import llvmlite.binding as llvm

    return llvm


def _initialize_llvm(llvm):
    try:
        llvm.initialize()
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()
    except Exception:
        llvm.initialize_all_targets()
        llvm.initialize_all_asmprinters()


def _sample_ir():
    return "\n".join(
        [
            'target triple = "x86_64-pc-windows-msvc"',
            'target datalayout = ""',
            "",
            "declare i32 @printf(i8*, ...)",
            '@fmt = private constant [6 x i8] c"%lld\\0a\\00"',
            "",
            "define i32 @main() {",
            "entry:",
            "  %fmt_ptr = bitcast [6 x i8]* @fmt to i8*",
            "  call i32 (i8*, ...) @printf(i8* %fmt_ptr, i64 42)",
            "  ret i32 0",
            "}",
        ]
    )


def test_llvmlite_target_machine_emits_object_file(tmp_path):
    llvm = _llvm()
    _initialize_llvm(llvm)

    target = llvm.targets.Target.from_default_triple()
    assert target.name

    target_machine = target.create_target_machine(opt=2)
    module = llvm.parse_assembly(_sample_ir())
    module.verify()

    obj = target_machine.emit_object(module)
    assert len(obj) > 0

    out_file = tmp_path / "test_out.o"
    out_file.write_bytes(obj)
    assert out_file.exists()
    assert out_file.stat().st_size == len(obj)
