# Sunkworks Research Sprint: Spin 4.0 & The Bleeding Edge

## 🎙️ Episode Objective
Synthesize the technical shift from "Legacy WASM" to the "Component Model" (WASI 0.2.0) using the Mecris Beta 4 migration as a high-stakes case study. 

**Mission**: Show how WebAssembly enables cross-language collaboration that moves beyond simple FFI, allowing Python and Rust devs to share the same immutable artifacts.

## 📄 Prerequisites
Before starting this sprint, the researcher MUST internalize:
👉 **[docs/RESEARCH_FOUNDATION_SPIN_V4.md](RESEARCH_FOUNDATION_SPIN_V4.md)**

---

## 1. The Component Model deep-dive
*   **The "World" Standard**: Research the `spin:up/http-trigger@4.0.0` world. What changed between this and the legacy triggers?
*   **WASI 0.2.0 Verification**: Confirm the exact specification of WASI HTTP 0.2.0. Is the `incoming-handler` export the definitive standard for all future WASM clouds?
*   **Changelog Audit**: Review the Spin releases from **v1.0 to v4.0**. Identify the specific "tipping points" where the Component Model became the primary focus. Summarize the major breaking changes in each leap (1->2, 2->3, 3->4).

## 2. The Hermeticity Challenge (SLSA)
*   **Air-Gapped Reproducibility**: Research tooling for creating **internal mirrors** of WASM dependencies. How can we produce the same Beta 4 artifacts without an internet connection?
*   **The "WASM Suit"**: Analyze how bundling the Python interpreter *inside* the WASM component creates a supply-chain-confident artifact compared to traditional container layering.

## 3. The Cloud Readiness Gap (The Friction)
*   **Runtime Lag**: Investigate the release cycle of the Fermyon Cloud runtime. Is there a documented delay between SDK releases and runtime support?
*   **Runtime Class Executors**: Research the `runtime-class-executor` configuration. Could specific CA certificate paths or executor fields explain our cloud-only `500` and `NotImplementedError`?

## 4. Final Show Grill (Audience Profiles)
Prepare talking points for these two distinct audiences:

### A. The "Zero-Rewrite" Python Developer
*   How does this enable a Python dev to contribute to a high-performance system without learning Rust?
*   Why is this different/better than old-school FFI?
*   Is the "WASM Tax" (the complex build command) worth the benefit?

### B. The WASM Architect
*   How do we prove our Beta 4 artifacts are now 100% reproducible and SLSA-verifiable?
*   What is the significance of the 4.0.0 release being the "first non-beta" moment for the component model in Python?

---
*Prompt Version: 1.1 (2026-04-25)*
