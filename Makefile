.PHONY: test test-python test-rust test-all

test: test-python test-rust
	@echo "✅ All tests complete"

test-python:
	@echo "🐍 Running Python tests (pytest)"
	PYTHONPATH=. .venv/bin/pytest

test-rust:
	@echo "🦀 Running Rust tests (Boris & Fiona)"
	$(MAKE) -C boris-fiona-walker test

test-all: test
