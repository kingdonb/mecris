# Mecris Research Foundation: The Spin v4 / WASM Component Migration

This document serves as the "Technical Ground Truth" for the Mecris Beta 4 migration to the WebAssembly Component Model (WASI 0.2.0) and Spin SDK v4. It captures the experimental findings, failures, and accidental discoveries of Session #47.

## 1. The Core Migration (The "Holy Grail")
Mecris successfully moved 4 Python logic components into immutable WASM binaries. This proved the "Zero-Rewrite" dream for Python logic is achievable in the Component Model.

### Verified Working (Local - Spin 4.0.0):
- **`review-pump-py`**: Primary logic component for language liability calculation.
- **`budget-governor-py`**: Port of the spend envelope logic (Soft/Hard caps).
- **`arabic-skip-counter`**: Database-backed component counting recent skips.
- **`log-message-py`**: New component for notification audit trail.

## 2. Experimental Failures & Hard Lessons

### A. The "Zombie" WASM State
During initial builds, components would return `NotImplementedError: handle_request requires WASM runtime (spin_sdk)`. 
- **Cause**: `try...except ImportError` blocks in `app.py`.
- **Finding**: `componentize-py` takes a memory snapshot of the initialized interpreter. If a dependency (like `spin_sdk`) is missing *at build time*, the error is caught and baked into the binary permanently.
- **Fix**: Remove all `try...except` guards around core SDK imports to ensure builds fail loudly rather than producing "Zombie" WASM.

### B. The Async Mandate (SDK 4.0.0)
The 4.0.0 release (April 2026) introduced major breaking changes to the Python SDK.
- **Findings**: 
    - `IncomingHandler` (v1) was replaced by `http.Handler` (v2).
    - `handle_request` **must** be `async def`.
    - Host functions (`variables.get`, `kv.open_default`, `postgres.query`, `http.send`) have all transitioned from synchronous to asynchronous.
    - Missing an `await` on these calls results in a `TypeError: 'Response' object can't be awaited` (internal SDK error) or a `RuntimeWarning: coroutine was never awaited`.

### C. The Environment Pollution Conflict
`componentize-py` is extremely sensitive to local file system state.
- **Finding**: The tool incorrectly scans parent directories for virtual environments or `componentize-py.toml` files, leading to `AssertionError: multiple componentize-py.toml files found`.
- **Fix**: Implemented the **Universal Clean Build** strategy—recursively nuking `.venv` and `__pycache__` before every build and using `uv venv --clear`.

## 3. The Cloud Readiness Gap
As of April 25, 2026, there is a divergence between local verified success and cloud production.
- **Fermyon Cloud**: Consistently returns `NotImplementedError` for SDK v4 binaries.
- **Akamai Functions**: Returns `500 Internal Server Error (guest not invoked)`.
- **Hypothesis**: The cloud runtimes may lag the SDK release (which was ~19 hours old at the time of testing) or require specific `runtime-class-executor` configurations (e.g., CA certificate paths) that were not present in our k3d/local environments.

## 4. Driver Evolution: DB Connectivity
The migration proved that native C-extension drivers (like `psycopg2`) are incompatible with the WASM runtime.
- **Success**: Swapped `psycopg2` for `spin_sdk.postgres`.
- **Constraint**: Requires explicitly passing `ParameterValue_Str` or similar variants to the `query` method.

---
*Created: 2026-04-24 | Updated: 2026-04-25*
