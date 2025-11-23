# TDG Configuration

## Project Information
- Language: Python
- Framework: None
- Test Framework: pytest

## Build Command
uv pip install -r requirements.txt

## Test Command
uv run pytest

## Single Test Command
uv run pytest -k "<test_name>"

## Coverage Command
pytest --cov=.

## Test File Patterns
- Test files: test_*.py, *_test.py
- Test directory: tests/