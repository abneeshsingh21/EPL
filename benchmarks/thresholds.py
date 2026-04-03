"""Threshold helpers for EPL benchmark regression checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


THRESHOLDS_PATH = Path(__file__).with_name("thresholds.json")


def load_thresholds(path: Path | None = None) -> Dict:
    with (path or THRESHOLDS_PATH).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_thresholds(payload: Dict, benchmark_names: List[str]) -> None:
    if "benchmarks" not in payload or not isinstance(payload["benchmarks"], dict):
        raise ValueError("threshold payload must contain a benchmarks object")
    missing = [name for name in benchmark_names if name not in payload["benchmarks"]]
    if missing:
        raise ValueError(f"missing thresholds for: {', '.join(missing)}")
    for name in benchmark_names:
        config = payload["benchmarks"][name]
        if "max_best_seconds" not in config:
            raise ValueError(f"threshold for {name} must contain max_best_seconds")
        if float(config["max_best_seconds"]) <= 0:
            raise ValueError(f"threshold for {name} must be > 0")


def compare_results(results: List[Dict], payload: Dict) -> List[Dict]:
    tolerance_factor = 1.0 + (float(payload.get("tolerance_percent", 0)) / 100.0)
    failures = []
    thresholds = payload["benchmarks"]
    for result in results:
        name = result["name"]
        if "error" in result:
            failures.append({
                "name": name,
                "reason": f"benchmark failed to run: {result['error']}",
            })
            continue
        allowed = float(thresholds[name]["max_best_seconds"]) * tolerance_factor
        best = float(result["best"])
        if best > allowed:
            failures.append({
                "name": name,
                "best": best,
                "allowed": allowed,
                "threshold": float(thresholds[name]["max_best_seconds"]),
            })
    return failures
