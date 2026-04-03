.PHONY: test test-all lint fmt fmt-check clean

# Run all tests
test:
	python tests/run_tests.py
	python tests/test_epl.py
	python -m pytest tests/test_vm.py -q
	python tests/test_compiler.py
	python tests/test_stability.py
	python tests/test_package_manager.py
	python tests/test_js_transpiler.py
	python -m pytest tests/test_kotlin.py -q
	python tests/test_comprehensive.py
	python tests/test_framework.py

# Quick test (just regression + v4)
test-quick:
	python tests/run_tests.py
	python tests/test_epl.py

# Lint EPL example files
lint:
	python main.py lint examples/

# Format EPL files (check only)
fmt-check:
	python main.py fmt examples/ --check

# Format EPL files (in place)
fmt:
	python main.py fmt examples/ --in-place

# Clean build artifacts
clean:
	rm -f *.o *.exe *.ll *.js *.kt
	rm -rf __pycache__ .pytest_cache
	rm -rf epl/__pycache__ tests/__pycache__
	rm -f test_output.txt test_tmp.txt test_out.o
