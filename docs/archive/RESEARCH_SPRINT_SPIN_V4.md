# Sunkworks Research Sprint: Spin 4.0 & The Bleeding Edge

## 🎙️ Episode Objective
Synthesize the technical shift from "Legacy WASM" to the "Component Model" (WASI 0.2.0) using the Mecris Beta 4 migration as a high-stakes case study. 

**Mission**: Mark the occasion! Spin 4.0.0 is out, and Mecris Beta 4 is right here at the right time. We want to show everyone what we've built, how special WebAssembly is (it's *not* just FFI!), and how it enables people using different programming languages to work together to do amazing things.

## 📄 Prerequisites
Before starting this sprint, the researcher MUST internalize:
👉 **[docs/RESEARCH_FOUNDATION_SPIN_V4.md](RESEARCH_FOUNDATION_SPIN_V4.md)**

---

## 1. The Component Model deep-dive
*   **The "World" Standard**: Research the `spin:up/http-trigger@4.0.0` world. What changed between this and the legacy triggers?
*   **WASI 0.2.0 Verification**: Confirm the exact specification of WASI HTTP 0.2.0. Is the `incoming-handler` export the definitive standard for all future WASM clouds?
*   **Changelog Audit**: Review the Spin releases from **v1.0 to v4.0**. Identify the specific "tipping points" where the Component Model became the primary focus, and understand the major breaking changes that led us to this "first non-beta" moment for the Python component model.

## 2. The Hermeticity Challenge (SLSA & Accountability)
*   **Air-Gapped Reproducibility**: Research tooling for creating **internal mirrors** for all the languages we use. How can we ensure we produce the exact same Beta 4 artifacts in an air-gapped environment?
*   **Supply Chain Confidence**: How do we guarantee that the dependencies we pull haven't been tampered with, and ensure we only install versions reviewed by a human?
*   **The "WASM Suit"**: Analyze how bundling the Python interpreter *inside* the WASM component directly advances our SLSA build level goals.

## 3. The Cloud Readiness Gap (The Friction)
*   **Runtime Lag**: Investigate the release cycle of the Fermyon Cloud runtime. Is there a documented delay between SDK releases and runtime support?
*   **Runtime Class Executors**: Research the `runtime-class-executor` configuration. Could specific CA certificate paths or executor fields explain our cloud-only `500` and `NotImplementedError`?

## 4. Final Show Grill (Audience Profiles)
Prepare talking points for these two distinct audiences:

### A. The "Zero-Rewrite" Python Developer
*   How does this empower a Python dev who doesn't feel capable of working with Rust to contribute to a high-performance, polyglot system?
*   Why is the Component Model fundamentally different—and better—than old-school Foreign Function Interfaces (FFI)?
*   Is the "WASM Tax" (the complex build command) worth the benefit of true collaboration without silos?

### B. The WASM Architect
*   You're the ones building the system to do what we want. Can you explain *how* WebAssembly makes this unique artifact sharing possible?
*   How do we prove our Beta 4 artifacts are now 100% reproducible and SLSA-verifiable?
*   Why is Spin 4.0.0 a watershed moment to celebrate?

---
*Prompt Version: 1.1 (2026-04-25)*
