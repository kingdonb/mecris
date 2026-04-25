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

## 3. Strategic Vision: Collaboration without Silos

The WASM Component Model (WASI 0.2.0) is not just a technical upgrade; it is a collaborative breakthrough.

### A. Bridging Language Silos
The target audience includes:
- **The "Zero-Rewrite" Python Developer**: Devs who want to contribute complex logic to high-performance systems without feeling intimidated by or needing to learn Rust or JS.
- **The WASM Architect**: Professionals building language-agnostic systems who can explain *why* this is different from traditional approaches.
- **Goal**: Show that these two groups can work together on the same system to do amazing things. WebAssembly is very special—it's not just a Foreign Function Interface (FFI) where languages awkwardly call each other; it's a true, shared, immutable artifact.

### B. Double-Down on Hermeticity (SLSA)
A core Mecris goal is achieving **SLSA Build Levels** to guarantee accountability in our supply chain.
- **Hermeticity & Air-Gapped Environments**: The ability to produce identical artifacts in an air-gapped environment using internal mirrors for all languages we use.
- **Supply Chain Confidence**: By hosting our own dependencies, we ensure they haven't been tampered with and that the exact versions we install have been explicitly reviewed by a human.
- **Verification**: WASM binaries provide the "WASM Suit" that makes Python logic reproducible and verifiable, directly advancing our SLSA goals.

## 4. The Cloud Readiness Gap
As of April 25, 2026, there is a divergence between local verified success and cloud production.
- **Fermyon Cloud**: Consistently returns `NotImplementedError` for SDK v4 binaries.
- **Akamai Functions**: Returns `500 Internal Server Error (guest not invoked)`.
- **Hypothesis**: The cloud runtimes may lag the SDK release (~19 hours old) or require specific `runtime-class-executor` configurations (e.g., CA certificate paths).

---
*Created: 2026-04-24 | Updated: 2026-04-25*
