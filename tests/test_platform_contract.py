from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPlatformContract(unittest.TestCase):
    def test_versioning_policy_defines_command_stability_labels(self):
        policy = (ROOT / "docs" / "versioning-policy.md").read_text(encoding="utf-8")
        self.assertIn("Stable commands:", policy)
        self.assertIn("Beta commands:", policy)
        self.assertIn("Experimental commands:", policy)
        self.assertIn("`run`", policy)
        self.assertIn("`ai`", policy)
        self.assertIn("`cloud`", policy)

    def test_security_policy_defines_response_targets(self):
        policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("48 hours", policy)
        self.assertIn("7 days", policy)
        self.assertIn("30 days", policy)
        self.assertIn("critical", policy.lower())
        self.assertIn("high", policy.lower())

    def test_release_checklist_references_benchmark_guard(self):
        checklist = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")
        self.assertIn("scripts/check_benchmark_thresholds.py", checklist)
