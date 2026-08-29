"""Tests for Phase 6: Cryptographic Package Signing, OS Sandboxing, and Formal Semantics."""

import pytest
import os
import tempfile
import json
from epl.crypto_signing import CryptoSigner, PackageSigner
from epl.sandbox_os import SandboxOS, ResourceLimits, SeccompFilter
from epl.formal_semantics import FormalSemantics, BigStepReducer, FormalEnv, SmallStepReducer
from epl.ast_nodes import Program, Literal, BinaryOp, VarDeclaration, VarAssignment


class TestCryptoSigning:
    """Tests for package signing, key generation, and verification."""

    def test_keypair_generation(self):
        priv_key, pub_key = CryptoSigner.generate_keypair()
        assert len(priv_key) == 64
        assert len(pub_key) == 64
        assert priv_key != pub_key

    def test_data_signing_and_verification(self):
        priv_key, pub_key = CryptoSigner.generate_keypair()
        data = b"EPL Standard Library Package Payload v11.0.0"

        sig = CryptoSigner.sign_data(data, priv_key)
        assert len(sig) == 128 or len(sig) == 64

        # Valid verification
        assert CryptoSigner.verify_signature(data, sig, pub_key) is True

        # Tampered data verification must fail
        tampered = data + b" malicious modification"
        assert CryptoSigner.verify_signature(tampered, sig, pub_key) is False

        # Wrong public key verification must fail
        _, other_pub_key = CryptoSigner.generate_keypair()
        assert CryptoSigner.verify_signature(data, sig, other_pub_key) is False

    def test_package_archive_signing_and_verification(self):
        priv_key, pub_key = CryptoSigner.generate_keypair()

        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_file = os.path.join(tmpdir, "testpkg.tar.gz")
            with open(pkg_file, "wb") as f:
                f.write(b"SAMPLE EPL COMPRESSED ARCHIVE CONTENT")

            # Sign package
            manifest = PackageSigner.sign_package(pkg_file, priv_key, "signer@epl-lang.org")
            assert manifest["algorithm"] == "Ed25519"
            assert manifest["signer"] == "signer@epl-lang.org"
            assert "archive_sha256" in manifest
            assert "signature" in manifest

            # Verify package with correct manifest
            assert PackageSigner.verify_package(pkg_file, manifest, pub_key) is True

            # Tamper with archive
            with open(pkg_file, "wb") as f:
                f.write(b"TAMPERED CONTENT")
            assert PackageSigner.verify_package(pkg_file, manifest, pub_key) is False


class TestOSSandboxing:
    """Tests for OS-level sandboxing, rlimits, and seccomp policies."""

    def test_resource_limits_configuration(self):
        limits = ResourceLimits(
            max_cpu_seconds=5,
            max_memory_bytes=64 * 1024 * 1024,
            max_file_size_bytes=10 * 1024 * 1024,
            max_open_files=100,
        )
        SandboxOS.apply_limits(limits)

    def test_seccomp_filter_policy(self):
        seccomp = SeccompFilter()
        policy = seccomp.generate_bpf_policy()
        assert "default_action" in policy
        assert policy["default_action"] == "SECCOMP_RET_KILL"
        assert "sys_read" in policy["allowed_syscalls"]
        assert "sys_write" in policy["allowed_syscalls"]
        assert "sys_execve" in policy["blocked_syscalls"]

    def test_drop_privileges(self):
        res = SandboxOS.drop_privileges()
        assert isinstance(res, bool)


class TestFormalSemantics:
    """Tests for Formal Operational Semantics and Big-Step evaluation."""

    def test_literal_reduction(self):
        reducer = BigStepReducer()
        env = FormalEnv()

        ast_lit = Literal(42)
        term = FormalSemantics.ast_to_formal(ast_lit)
        res_env, val, rule = reducer.eval(term, env)

        assert val == 42
        assert rule == "Const-Eval"

    def test_binary_op_reduction(self):
        reducer = BigStepReducer()
        env = FormalEnv()

        ast_bin = BinaryOp(Literal(15), "+", Literal(27))
        term = FormalSemantics.ast_to_formal(ast_bin)
        res_env, val, rule = reducer.eval(term, env)

        assert val == 42
        assert rule == "BinOp-Eval"

    def test_variable_declaration_and_lookup(self):
        reducer = BigStepReducer()
        env = FormalEnv()

        ast_decl = VarDeclaration(name="x", value=Literal(100))
        term_decl = FormalSemantics.ast_to_formal(ast_decl)
        res_env, val, rule = reducer.eval(term_decl, env)

        assert rule == "Var-Decl"
        assert res_env.lookup("x") == 100

    def test_small_step_trace(self):
        ast_bin = BinaryOp(Literal(10), "*", Literal(20))
        term = FormalSemantics.ast_to_formal(ast_bin)

        step_reducer = SmallStepReducer()
        trace = step_reducer.step_trace(term)
        assert len(trace) >= 1
        final_state, final_term = trace[-1]
        assert final_term.val == 200

    def test_formal_soundness_proof(self):
        prog = Program(
            statements=[
                VarDeclaration(
                    name="ans",
                    value=BinaryOp(Literal(20), "+", Literal(22)),
                )
            ]
        )
        proof = FormalSemantics.prove_soundness(prog)
        assert proof["proved"] is True
        assert proof["final_state"]["ans"] == 42
        assert len(proof["proof_steps"]) >= 1
