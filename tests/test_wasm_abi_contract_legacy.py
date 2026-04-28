"""
WASM ABI Contract Tests (legacy-cloud) — yebyen/mecris#299

Verifies that all WASM component sources on the `legacy-cloud` branch declare
`handle_request` as a synchronous function (`def`, not `async def`), confirming
SDK v3 compliance.

## Why this matters: The Dual-Track ABI Enforcement

Per docs/CI_CD_EVOLUTION_PLAN.md, Mecris maintains two release tracks:
  - main         → SDK v4 (async), targeting Spin v4 hosts (canary)
  - legacy-cloud → SDK v3 (sync),  targeting Spin v3 hosts (stable)

This test reads component sources from the `legacy-cloud` branch using
`git show origin/legacy-cloud:<path>` — no checkout required. It runs on
the main branch CI, asserting the counter-invariant: legacy-cloud must
remain synchronous until explicitly sunset.

The dual-track enforcement is:
  - test_wasm_abi_contract.py        → main is async (SDK v4)
  - test_wasm_abi_contract_legacy.py → legacy-cloud is sync (SDK v3)

When both tests pass, the dual-track is healthy. When the cloud provider
upgrades, legacy-cloud is sunset and this test is retired.

## Components covered (same 4, read from legacy-cloud branch)
  1. mecris-go-spin/arabic-skip-counter/app.py
  2. poc/wasm/log-message-py/app.py
  3. poc/wasm/budget-governor-py/app.py
  4. poc/wasm/review-pump-py/app.py
"""

import ast
import subprocess
import pytest


WASM_COMPONENT_PATHS = [
    ("arabic-skip-counter", "mecris-go-spin/arabic-skip-counter/app.py"),
    ("log-message-py", "poc/wasm/log-message-py/app.py"),
    ("budget-governor-py", "poc/wasm/budget-governor-py/app.py"),
    ("review-pump-py", "poc/wasm/review-pump-py/app.py"),
]

_LEGACY_BRANCH = "origin/legacy-cloud"


def _read_from_branch(branch: str, path: str) -> str:
    """Read file content from a git branch without checking it out."""
    result = subprocess.run(
        ["git", "show", f"{branch}:{path}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(
            f"Cannot read {path} from {branch}: {result.stderr.strip()}. "
            f"Ensure 'git fetch origin' has been run and the branch exists."
        )
    return result.stdout


def _find_handle_request(source: str, label: str):
    """Return the AST node for HttpHandler.handle_request, or None."""
    tree = ast.parse(source, filename=label)
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


@pytest.mark.parametrize("component_name,rel_path", WASM_COMPONENT_PATHS)
class TestWasmAbiContractLegacy:
    """Assert SDK v3 sync ABI on all legacy-cloud branch WASM components."""

    def test_handle_request_is_sync(self, component_name, rel_path):
        """handle_request must be plain `def` (SDK v3 synchronous interface)."""
        source = _read_from_branch(_LEGACY_BRANCH, rel_path)
        label = f"{_LEGACY_BRANCH}:{rel_path}"
        node = _find_handle_request(source, label)
        assert node is not None, (
            f"{component_name}: HttpHandler.handle_request not found in "
            f"{label}. Has the class been renamed or removed?"
        )
        assert isinstance(node, ast.FunctionDef), (
            f"{component_name}: handle_request is `async def` (SDK v4 coroutine) "
            f"on legacy-cloud branch. It must be plain `def` (sync, SDK v3). "
            f"If this component was upgraded to async, it belongs on main only, "
            f"and the legacy-cloud copy must be reverted to the sync API."
        )

    def test_handler_class_exists(self, component_name, rel_path):
        """HttpHandler class must be present in the legacy-cloud source."""
        source = _read_from_branch(_LEGACY_BRANCH, rel_path)
        label = f"{_LEGACY_BRANCH}:{rel_path}"
        tree = ast.parse(source, filename=label)
        handler_classes = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "HttpHandler"
        ]
        assert len(handler_classes) >= 1, (
            f"{component_name}: HttpHandler class not found in {label}. "
            f"Has the component been restructured?"
        )
