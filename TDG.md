# TDG Configuration

## Project Information
- Language: Python
- Framework: FastAPI/Python
- Test Framework: pytest

## Build Command
uv pip install -r requirements.txt pytest-cov pytest-asyncio

## Test Command
PYTHONPATH=. .venv/bin/pytest

## Single Test Command
PYTHONPATH=. .venv/bin/pytest <file_path> -v

## Coverage Command
PYTHONPATH=. .venv/bin/pytest --cov=. --cov-report=term-missing

## Test File Patterns
- Test files: test_*.py, *_test.py
- Test directory: tests/

## Execution Notes
- Always prefix test commands with `PYTHONPATH=.` to ensure local modules are discoverable.
- Use the `.venv/bin/pytest` binary directly to ensure the correct environment is used.
- For async tests, `pytest-asyncio` is required and the `pytest.ini` is already configured for auto-mode.
