"""
EPL Benchmark Suite Runner
Runs standardized benchmark programs and reports timing results.
Supports JSON output for CI/regression tracking.
"""

import contextlib
import io
import os
import sys
import time
import json

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.errors import set_source_context


BENCHMARKS_DIR = os.path.dirname(os.path.abspath(__file__))

BENCHMARK_FILES = [
    'fibonacci.epl',
    'strings.epl',
    'lists.epl',
    'recursion.epl',
    'oop.epl',
]


def run_single(filepath: str, runs: int = 5, warmup: int = 1) -> dict:
    """Run a single benchmark and return timing results."""
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    name = os.path.basename(filepath)
    set_source_context(source, filepath)

    def _execute_once():
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        interp = Interpreter()
        with contextlib.redirect_stdout(io.StringIO()):
            interp.execute(program)

    # Warmup
    for _ in range(warmup):
        try:
            _execute_once()
        except Exception:
            return {'name': name, 'error': 'warmup failed', 'times': []}

    # Timed runs
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        _execute_once()
        times.append(time.perf_counter() - t0)

    return {
        'name': name,
        'runs': runs,
        'warmup': warmup,
        'best': min(times),
        'worst': max(times),
        'avg': sum(times) / len(times),
        'times': times,
    }


def run_suite(runs: int = 5, warmup: int = 1, json_output: bool = False):
    """Run all benchmarks in the suite."""
    results = []

    if not json_output:
        print(f"  EPL Benchmark Suite")
        print(f"  Runs: {runs}, Warmup: {warmup}")
        print("  " + "=" * 55)

    for filename in BENCHMARK_FILES:
        filepath = os.path.join(BENCHMARKS_DIR, filename)
        if not os.path.isfile(filepath):
            if not json_output:
                print(f"  SKIP: {filename} (file not found)")
            continue

        result = run_single(filepath, runs=runs, warmup=warmup)
        results.append(result)

        if not json_output:
            if 'error' in result:
                print(f"  {result['name']:20s}  FAILED: {result['error']}")
            else:
                print(f"  {result['name']:20s}  best={result['best']:.4f}s  avg={result['avg']:.4f}s  worst={result['worst']:.4f}s")

    if not json_output:
        print("  " + "=" * 55)

    if json_output:
        output = {
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'runs': runs,
            'warmup': warmup,
            'benchmarks': results,
        }
        print(json.dumps(output, indent=2))

    return results


def save_results(results: list, output_path: str):
    """Save benchmark results to a JSON file for regression tracking."""
    output = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'benchmarks': results,
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)


if __name__ == '__main__':
    json_mode = '--json' in sys.argv
    runs = 5
    for arg in sys.argv[1:]:
        if arg.startswith('--runs='):
            runs = int(arg.split('=')[1])
    run_suite(runs=runs, json_output=json_mode)
