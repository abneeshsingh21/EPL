"""Benchmark smoke tests for release and CI baseline tracking."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from benchmarks.run_benchmarks import BENCHMARK_FILES, run_suite, save_results
from benchmarks.thresholds import compare_results, load_thresholds, validate_thresholds


REPO_ROOT = Path(__file__).resolve().parents[1]


class TestBenchmarkBaselines(unittest.TestCase):
    def test_thresholds_cover_registered_benchmarks(self):
        thresholds = load_thresholds()
        validate_thresholds(thresholds, BENCHMARK_FILES)
        self.assertEqual(sorted(thresholds["benchmarks"].keys()), sorted(BENCHMARK_FILES))

    def test_benchmark_results_fit_repo_thresholds(self):
        thresholds = load_thresholds()
        validate_thresholds(thresholds, BENCHMARK_FILES)
        with contextlib.redirect_stdout(io.StringIO()):
            results = run_suite(runs=1, warmup=0)
        failures = compare_results(results, thresholds)
        self.assertEqual(failures, [])

    def test_benchmark_suite_reports_registered_inputs(self):
        with contextlib.redirect_stdout(io.StringIO()):
            results = run_suite(runs=1, warmup=0)

        self.assertEqual([result["name"] for result in results], BENCHMARK_FILES)
        for result in results:
            self.assertNotIn("error", result, result)
            self.assertEqual(result["runs"], 1)
            self.assertEqual(result["warmup"], 0)
            self.assertEqual(len(result["times"]), 1)
            self.assertGreater(result["best"], 0.0)
            self.assertGreaterEqual(result["worst"], result["best"])
            self.assertGreaterEqual(result["avg"], result["best"])

    def test_benchmark_results_can_be_saved_for_release_tracking(self):
        with contextlib.redirect_stdout(io.StringIO()):
            results = run_suite(runs=1, warmup=0)

        with tempfile.TemporaryDirectory(prefix="epl_bench_") as tmpdir:
            output_path = Path(tmpdir) / "benchmark-results.json"
            save_results(results, str(output_path))
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertIn("timestamp", payload)
        self.assertEqual(len(payload["benchmarks"]), len(BENCHMARK_FILES))
        self.assertEqual(
            [result["name"] for result in payload["benchmarks"]],
            BENCHMARK_FILES,
        )

    def test_bench_cli_json_output_is_machine_readable(self):
        result = subprocess.run(
            [sys.executable, "-m", "epl", "bench", "--json", "--runs=1"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        self.assertEqual(result.returncode, 0, output)

        payload = json.loads(result.stdout)
        self.assertEqual(payload["runs"], 1)
        self.assertEqual(payload["warmup"], 1)
        self.assertEqual(
            [result["name"] for result in payload["benchmarks"]],
            BENCHMARK_FILES,
        )

    def test_threshold_guard_script_emits_machine_readable_json(self):
        result = subprocess.run(
            [sys.executable, "scripts/check_benchmark_thresholds.py", "--json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        self.assertEqual(result.returncode, 0, output)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(sorted(payload["thresholds"]["benchmarks"].keys()), sorted(BENCHMARK_FILES))
