"""
WASM ABI Contract Tests — yebyen/mecris#298

Verifies that all WASM component sources on `main` declare `handle_request`
as an async coroutine (`async def`), confirming SDK v4 compliance.

## Why this matters: The Negative E2E Tripwire

Per docs/CI_CD_EVOLUTION_PLAN.md, Mecris maintains two release tracks:
  - main       → SDK v4 (async), targeting Spin v4 hosts (canary)
  - legacy-cloud → SDK v3 (sync), targeting Spin v3 hosts (stable)

The v3 host ABI requires `def handle_request` (synchronous).
The v4 host ABI requires `async def handle_request` (coroutine).

Loading a v4 component into a v3 host produces a specific ABI crash:
    [Error] Could not link 'component': import "fermyon:spin/http@2.0.0"
    has the wrong type. expected a function but found a coroutine.

This static contract test is the bot-implementable precursor. The full
negative E2E tripwire (asserting the cloud host fails with the above error
until providers upgrade to v4) requires Fermyon/Akamai infrastructure and
is human-executed as part of the dual-track tagging live session.

When the cloud provider silently upgrades to SDK v4 support, this negative
test will "pass" at the cloud layer, signaling that `legacy-cloud` can be
sunset and `main` promoted to GA as v0.1.0.

## Components covered
  1. mecris-go-spin/arabic-skip-counter/app.py
  2. poc/wasm/log-message-py/app.py
  3. poc/wasm/budget-governor-py/app.py
  4. poc/wasm/review-pump-py/app.py
"""

import ast
import os
import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

WASM_COMPONENTS = [
    (
        "arabic-skip-counter",
        os.path.join(_REPO_ROOT, "mecris-go-spin", "arabic-skip-counter", "app.py"),
    ),
    (
        "log-message-py",
        os.path.join(_REPO_ROOT, "poc", "wasm", "log-message-py", "app.py"),
    ),
    (
        "budget-governor-py",
        os.path.join(_REPO_ROOT, "poc", "wasm", "budget-governor-py", "app.py"),
    ),
    (
        "review-pump-py",
        os.path.join(_REPO_ROOT, "poc", "wasm", "review-pump-py", "app.py"),
    ),
]


def _find_handle_request(source_path: str):
    """Return the AST node for HttpHandler.handle_request, or None."""
    with open(source_path) as f:
        tree = ast.parse(f.read(), filename=source_path)

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name != "HttpHandler":
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name == "handle_request":
                    return item
    return None


@pytest.mark.parametrize("component_name,app_path", WASM_COMPONENTS)
class TestWasmAbiContract:
    """Assert SDK v4 async ABI on all main-branch WASM components."""

    def test_handle_request_is_async(self, component_name, app_path):
        """handle_request must be `async def` (SDK v4 coroutine interface)."""
        assert os.path.exists(app_path), (
            f"{component_name}: app.py not found at {app_path}"
        )
        node = _find_handle_request(app_path)
        assert node is not None, (
            f"{component_name}: HttpHandler.handle_request not found in {app_path}"
        )
        assert isinstance(node, ast.AsyncFunctionDef), (
            f"{component_name}: handle_request is `def` (sync/v3), expected `async def` (v4). "
            f"main branch must use SDK v4 async API. "
            f"If this component was downgraded to sync, revert the change. "
            f"Sync components belong on the legacy-cloud branch only."
        )

    def test_handler_class_exists(self, component_name, app_path):
        """HttpHandler class must be present in the source."""
        assert os.path.exists(app_path), (
            f"{component_name}: app.py not found at {app_path}"
        )
        with open(app_path) as f:
            tree = ast.parse(f.read(), filename=app_path)

        handler_classes = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "HttpHandler"
        ]
        assert len(handler_classes) >= 1, (
            f"{component_name}: HttpHandler class not found in {app_path}"
        )
