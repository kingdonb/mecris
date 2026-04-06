# Mecris Contributing Guide (The Procedural Law)

## 1. The Standard Bus (UniFFI/WIT)
To avoid the "Three Jobs" tax (Python, Rust, Kotlin), all shared business logic MUST be centralized in the `mecris-core` Rust crate. 

*   **The Engine**: New logic is portably implemented in `mecris-core`.
*   **The Shells**: Use **UniFFI** to generate bindings for the Android app (Kotlin) and the MCP (Python).
*   **The Cloud**: Use **WIT** to export logic for the Spin WASM components.
*   **First-to-Contract**: Any developer (Python "Scout" or Rust "Engine") who implements a new shared feature MUST define its interface (UDL or WIT) as the primary contract.

## 2. Test-Driven Generation (TDG)
We follow a strict Red-Green-Refactor cycle. No implementation is accepted without a corresponding verification block.

1.  **Red**: Define the test case or reproduction script.
2.  **Green**: Implement the minimal code to satisfy the test.
3.  **Refactor**: Clean up and optimize while maintaining the green state.

## 3. Science Cloud Alignment
We are building a "Science Cloud" infrastructure. Logic should be deterministic, language-neutral, and optimized for distributed execution via MCP servers.

## 4. Governance
*   **SOULE.md** is the living manifesto for high-level vision.
*   **CONTRIBUTING.md** is the procedural law for all agents and humans.
*   **Makefile** is the ultimate enforcer of these laws.
