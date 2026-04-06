# Feature Specification: Logic Vacuuming (v1.0)
**Status:** DRAFT (Reverse-Engineered from Session Logs)
**Date:** 2026-04-05
**Feature ID:** SYS-004 (Python-to-WASM Logic Migration)

## 1. Intent
Following the "Useless Architecture" pattern, Logic Vacuuming is the process of consolidating business logic into a single, language-agnostic source of truth (WASM). This prevents the "three jobs instead of two" problem by allowing Python development code to be compiled directly for cloud and mobile deployment.

## 2. Toolchain & Workflow

### 2.1 Toolchain
*   **`componentize-py`**: The primary tool for compiling Python code into WebAssembly components.
*   **WASI HTTP**: The standard interface for creating HTTP-triggered WASM components (Spin).

### 2.2 The "Vacuum" Loop
1.  **Develop in Python**: All logic (e.g., `ReviewPump` calculations) is first implemented and tested in the Python MCP vanguard.
2.  **Define WIT**: A WebAssembly Interface (WIT) is defined to export the required functions.
3.  **Compile to WASM**: The Python logic is compiled using `componentize-py`.
4.  **Deploy to Spin**: The `.wasm` component is deployed to Fermyon Spin for high-availability cloud access.

## 3. Logic Targets
*   **`review-pump`**: The core velocity calculation for Clozemaster clearance.
*   **`arabic-skip-counter`**: Logic for determining if an Arabic reminder can be skipped based on recent activity.

## 4. Success Criteria
*   **SC-001**: Logic is proven consistent across the Python MCP and the Spin WASM deployment.
*   **SC-002**: Reduction in manually maintained Rust logic in the `mecris-go-spin` directory.
*   **SC-003**: Successful compilation of Python components with embedded dependencies (e.g., `httpx`).

## 5. Architectural Mandate
Business logic MUST NOT be written directly in Rust for the Spin cloud if it can be written in Python and vacuumed. Rust is reserved for infrastructure-level shim code or performance-critical bottlenecks where Python is insufficient.
