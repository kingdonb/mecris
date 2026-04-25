# Sunkworks Research Sprint: Spin 4.0 & The Bleeding Edge

## 🎙️ Episode Objective
Synthesize the technical shift from "Legacy WASM" to the "Component Model" (WASI 0.2.0) using the Mecris Beta 4 migration as a high-stakes case study.

## 📄 Prerequisites
Before starting this sprint, the researcher MUST internalize:
👉 **[docs/RESEARCH_FOUNDATION_SPIN_V4.md](RESEARCH_FOUNDATION_SPIN_V4.md)**

---

## 1. The Component Model deep-dive
*   **The "World" Standard**: Research the `spin:up/http-trigger@4.0.0` world. What changed between this and the legacy triggers? Why did our build require explicit WIT directory provision?
*   **WASI 0.2.0 Verification**: Confirm the exact specification of WASI HTTP 0.2.0. Is the `incoming-handler` export the definitive standard for all future WASM clouds?

## 2. The Cloud Readiness Gap (The Friction)
*   **Runtime Lag**: Investigate the release cycle of the Fermyon Cloud runtime. Is there a documented delay between SDK releases and runtime support?
*   **Runtime Class Executors**: Research the `runtime-class-executor` configuration mentioned by Fermyon/Akamai engineers. Could missing CA certificate paths or executor fields explain our cloud-only `500` and `NotImplementedError`?
*   **Cross-Cloud Audit**: Compare Akamai Functions' "Edge" runtime against Fermyon's "Legacy" cloud. Which platform is closer to the WASI 0.2.0 baseline?

## 3. Hermeticity & SLSA
*   **The "WASM Suit" Theory**: Re-evaluate the hermeticity of Python in WASM. Is a memory-snapshotted WASM binary truly "SLSA Level 3" reproducible? 
*   **Dependency Injection**: How does the "Universal Clean Build" (nuking environments before building) affect our build integrity scores?

## 4. Final Show Grill
To prepare for the Sunkworks recording, answer these:
1.  **Field Report vs. Victory Lap**: How do we balance the "Holy Grail" success of moving Python logic into WASM with the "Brutal Reality" of cloud failure?
2.  **The "Stupid Mistake" Hypothesis**: Identify potential configuration gaps in our `spin.toml` or `Makefile` that might be perfectly legal locally but illegal in a hardened cloud executor.
3.  **The "Zero-Rewrite" Dream**: Is this actually achievable for the average Python dev, or is the "WASM Component Model" tax still too high for mainstream adoption?

---
*Prompt Version: 1.0 (2026-04-25)*
