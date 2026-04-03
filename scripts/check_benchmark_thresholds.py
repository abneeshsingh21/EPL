from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.run_benchmarks import BENCHMARK_FILES, run_suite
from benchmarks.thresholds import compare_results, load_thresholds, validate_thresholds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check EPL benchmark results against repo thresholds.")
    parser.add_argument("--runs", type=int, default=1, help="Benchmark runs per input.")
    parser.add_argument("--warmup", type=int, default=0, help="Warmup runs per input.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    thresholds = load_thresholds()
    validate_thresholds(thresholds, BENCHMARK_FILES)
    if args.json:
        with contextlib.redirect_stdout(io.StringIO()):
            results = run_suite(runs=args.runs, warmup=args.warmup, json_output=False)
    else:
        results = run_suite(runs=args.runs, warmup=args.warmup, json_output=False)
    failures = compare_results(results, thresholds)
    payload = {
        "ok": not failures,
        "runs": args.runs,
        "warmup": args.warmup,
        "thresholds": thresholds,
        "failures": failures,
        "benchmarks": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if failures:
            print("Benchmark threshold failures:")
            for failure in failures:
                print(f"- {failure['name']}: best={failure.get('best')} allowed={failure.get('allowed')} reason={failure.get('reason', '')}".rstrip())
        else:
            print("Benchmark thresholds passed.")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
