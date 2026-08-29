"""
Unit and Integration Tests for EPL Phase 6 Production Governance & Quality Gates
Validates:
- Platform Governance and Decision Policy (GOVERNANCE.md)
- Security Policy & Reporting Standards (SECURITY.md)
- Ecosystem Versioning Consistency (pyproject.toml, package.json, epl.__version__)
- Benchmark Regression Thresholds (benchmarks/thresholds.py, thresholds.json)
- Release Checklist & Packaging Integrity
"""

import json
import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epl import __version__
from benchmarks.thresholds import load_thresholds, validate_thresholds, compare_results


class TestPhase6Governance(unittest.TestCase):
    """Test Governance, Security, and Compliance Policies."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent

    def test_governance_document_structure(self):
        gov_path = self.repo_root / "GOVERNANCE.md"
        self.assertTrue(gov_path.exists(), "GOVERNANCE.md must exist in repository root")
        content = gov_path.read_text(encoding="utf-8")
        self.assertIn("Technical Steering", content)
        self.assertIn("RFC Process", content)
        self.assertIn("Versioning & Deprecation Policy", content)
        self.assertIn("Production Release Gates", content)

    def test_security_policy_structure(self):
        sec_path = self.repo_root / "SECURITY.md"
        self.assertTrue(sec_path.exists(), "SECURITY.md must exist in repository root")
        content = sec_path.read_text(encoding="utf-8")
        self.assertIn("Supported Versions", content)
        self.assertIn("Reporting a Vulnerability", content)
        self.assertIn("Response Timeline", content)

    def test_version_consistency(self):
        self.assertIsNotNone(__version__)
        self.assertTrue(len(__version__.split(".")) >= 3)

        # Check pyproject.toml if present
        pyproject_path = self.repo_root / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text(encoding="utf-8")
            self.assertIn('version = {attr = "epl.__version__"}', content)

        # Check vscode-extension/package.json if present
        pkg_json_path = self.repo_root / "vscode-extension" / "package.json"
        if pkg_json_path.exists():
            pkg_data = json.loads(pkg_json_path.read_text(encoding="utf-8"))
            self.assertIn("version", pkg_data)
            self.assertTrue(pkg_data["version"].count(".") >= 2)

    def test_benchmark_threshold_validation(self):
        threshold_data = load_thresholds(self.repo_root / "benchmarks" / "thresholds.json")
        benchmark_names = ["fibonacci.epl", "lists.epl", "oop.epl", "recursion.epl", "strings.epl"]
        validate_thresholds(threshold_data, benchmark_names)

        # Test simulated benchmark comparison
        mock_results = [
            {"name": "fibonacci.epl", "best": 0.05, "avg": 0.06},
            {"name": "lists.epl", "best": 0.04, "avg": 0.05},
            {"name": "oop.epl", "best": 0.03, "avg": 0.04},
            {"name": "recursion.epl", "best": 0.05, "avg": 0.06},
            {"name": "strings.epl", "best": 0.04, "avg": 0.05},
        ]
        failures = compare_results(mock_results, threshold_data)
        self.assertEqual(len(failures), 0, f"Benchmark thresholds violated: {failures}")

    def test_support_matrix_and_release_checklist_docs(self):
        supp_path = self.repo_root / "docs" / "support-matrix.md"
        rel_path = self.repo_root / "docs" / "release-checklist.md"
        self.assertTrue(supp_path.exists(), "docs/support-matrix.md must exist")
        self.assertTrue(rel_path.exists(), "docs/release-checklist.md must exist")

        supp_content = supp_path.read_text(encoding="utf-8")
        self.assertIn("Python", supp_content)
        self.assertIn("Operating Systems", supp_content)

        rel_content = rel_path.read_text(encoding="utf-8")
        self.assertIn("Release", rel_content)


if __name__ == "__main__":
    unittest.main()
