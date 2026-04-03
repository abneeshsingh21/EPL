# EPL Benchmark Baselines

This document defines the benchmark suites that must be tracked across releases.

## Baseline Commands

Interpreter / VM comparison:

- `epl benchmark benchmarks/fibonacci.epl`

Benchmark suite:

- `epl bench`
- `epl bench --json`
- `python -m pytest tests/test_benchmark_baselines.py -q`
- `python scripts/check_benchmark_thresholds.py --json`

Profiling:

- `epl profile benchmarks/fibonacci.epl`

## Required Areas

Every release should track these categories:

- interpreter execution
- bytecode VM execution
- native compile time
- package install time
- web request handling latency on the maintained reference backend app
- web request handling latency on the maintained reference fullstack app served through `epl serve`
- Android project generation time for the maintained reference app

## Current Benchmark Inputs

In-repo benchmark programs:

- `benchmarks/fibonacci.epl`
- `benchmarks/lists.epl`
- `benchmarks/oop.epl`
- `benchmarks/recursion.epl`
- `benchmarks/strings.epl`

## Release Rule

- do not merge performance-sensitive changes without checking the relevant benchmark category
- record notable regressions and improvements in release notes
- treat threshold breaches as release blockers unless there is a documented reason and an updated threshold/baseline review
- keep `epl bench --json` machine-readable so CI can publish a baseline artifact for each release validation run

## Thresholds

Threshold data lives in `benchmarks/thresholds.json`.

Current guard configuration:

| Benchmark | Max Best Seconds | Tolerance |
|-----------|------------------|-----------|
| `fibonacci.epl` | `0.25` | `20%` |
| `strings.epl` | `0.25` | `20%` |
| `lists.epl` | `0.15` | `20%` |
| `recursion.epl` | `0.05` | `20%` |
| `oop.epl` | `0.75` | `20%` |

Guard command:

- `python scripts/check_benchmark_thresholds.py`
- `python scripts/check_benchmark_thresholds.py --json`

The guard compares benchmark `best` time against `max_best_seconds * (1 + tolerance_percent/100)`.
