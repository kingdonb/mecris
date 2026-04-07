# Mecris Contributing Guide (The Procedural Law)

## 1. Python First, Rust for the Standard Bus
Mecris is fundamentally driven by its MCP architecture, which is built on Python (FastMCP and FastAPI). We strongly encourage Python developers to write Python to solve their own problems. 
- **The Core MCP:** Python is the primary language for prototyping, building the MCP, and rapidly iterating on new features. 
- **Python WASM (componentize-py):** Deploying Python to the Science Cloud (Fermyon Spin) using `componentize-py` is a first-class strategy. A 30MB WASM payload is perfectly acceptable to host existing capabilities in a way that can be reused by other parts. We do not wish to see this obviated.
- **The Standard Bus (UniFFI/WIT):** When business logic needs to be shared across all "Three Jobs" (the Python MCP, the Kotlin Android app, and the Rust-backed Cloud), it should be centralized into the `mecris-core` Rust crate.
  - *Prototyping*: New features can be prototyped in Python-only. 
  - *Maturation*: Once mature, logic that requires true cross-platform sharing should conform to the Standard Bus philosophy by being translated into the `mecris-core` Rust crate.
  - *Integration*: Use **UniFFI** to generate bindings for Android (Kotlin) and MCP (Python), and **WIT** to export logic for Spin WASM.

## 2. Test-Driven Generation (TDG)
We follow a strict Red-Green-Refactor cycle. No implementation is accepted without a corresponding verification block.

1.  **Red**: Define the test case or reproduction script.
2.  **Green**: Implement the minimal code to satisfy the test.
3.  **Refactor**: Clean up and optimize while maintaining the green state.

## 3. Science Cloud Alignment
We are building a "Science Cloud" infrastructure. Logic should be deterministic, language-neutral (at the boundary), and optimized for distributed execution via MCP servers.

## 4. Governance
*   **SOULE.md** is the living manifesto for high-level vision.
*   **CONTRIBUTING.md** is the procedural law for all agents and humans.
*   **Makefile** is the ultimate enforcer of these laws.