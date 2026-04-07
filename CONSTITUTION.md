# Mecris Constitution (Draft 2 - The Unified Blueprint)

## Core Principles

### I. Reality Enforcement (The Clinical Witness)
Mecris is not a savior; it is a witness. If the human fails, the system must record that failure with clinical precision. We do not forge "0.0 heartbeats" to prevent derailment. The Ghost Archivist ensures the internal record (Neon DB / K8s CRDs) matches reality, accepting that accurate derailments are a valid, necessary outcome.

### II. Physical Supremacy
The highest priority of the system is the user's physical well-being. Every interaction and autonomous session must prioritize physical activity (e.g., dog walks) before technical or secondary goals.

### III. Zero-Split-Brain (The WASM Axiom)
Core business logic (The "Brain") MUST be encapsulated in a WebAssembly (WASM) component using the Component Model (WIT) or Extism. This logic runs identically across every part of the stack—Kubernetes Operators, the Spin API, the MCP Server, the CLI, and the Android Client.
*   **Host Ignorance:** The WASM Brain must have no knowledge of its host. It consumes structured data and produces structured data. All I/O (Network, API, Time) is handled exclusively by the host environment.
*   **Logic Vacuuming:** Business logic may be rapidly prototyped in Python (The Vanguard) but must be "vacuumed" into the WASM Brain to ensure a single, highly performant source of truth.

### IV. Continuous Operation (The Operator & CLI)
Mecris must operate continuously and independently of external "second systems" (like an autonomous LLM loop).
*   **The Operator:** A Kubernetes controller (reconciler) loads the WASM Brain to constantly monitor and reconcile the state of the system (CRDs) in the background.
*   **The CLI:** A robust terminal interface provides power-user access and administrative control using the exact same shared logic.

### V. Cohesion over Divergence
We do not create divergent architectural forks to bypass security or integration constraints. "Divergence is confusion. Cohesion is our goal now."
*   **Unified Identity:** Authentication and authorization must use a cohesive OIDC provider (e.g., Pocket-ID). We do not build unauthenticated islands or ad-hoc security mechanisms.
*   **Secure Bridges:** Architectural limitations (e.g., calling a Kubernetes API from a Spin component requiring internal TLS/CA trust) must be solved cohesively—whether via a TLS-terminated proxy, CA injection, or a dedicated Bridge Component—never by degrading the architecture or disabling security.

### VI. Test-Driven Generation (TDG) & HCAT
*   **The Harsh Reality Check:** Stop thinking. Start testing. All code changes must be verified by automated tests *before* and *after* implementation (Red-Green-Refactor).
*   **Hardened Containerized Autonomous Turns (HCAT):** All autonomous work must run in ephemeral, isolated containers with SHA-pinned base images and strict lockfile verification to limit blast radius.

### VII. The Lab of Excellence (Fork-First Development)
Mecris is a marathon. Agents should "cook" features in their own forks (`yebyen/mecris`). Pull requests to the upstream `main` branch are only opened when a feature represents a complete, verified unit of progress.

## Feature Domains

### The Nag Ladder
A multi-tier notification system (Gentle -> Escalated -> Emergency) driven by the WASM Brain's idle-time detection and runway urgency.

### The Majesty Cake
A daily aggregate status widget requiring a unified "All Clear" across all tracked modalities (Steps, Arabic, Greek).

### The Ghost Archivist
A deterministic background process that forces daily reconciliation between external APIs (Beeminder, Clozemaster) and the internal state, enforcing reality at the day boundary.

## Governance
*   This Constitution supersedes all other documentation.
*   Amendments require a formal session log entry and a version bump.
*   All PRs must be reviewed against these principles to ensure absolute cohesion.

**Version**: Draft 2 | **Status**: Pending Ratification
