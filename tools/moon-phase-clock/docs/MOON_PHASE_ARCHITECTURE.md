# 🌕 The Useless Moon Phase Clock: Architecture Blueprint

*An implementation of the "Zero-Split-Brain" Vind-Box Architecture, infused with the lore of the Mecris Torment Matrix.*

This project implements a highly over-engineered, mathematically precise Moon Phase Clock. It exists to prove the viability of a true "Write Once, Run Everywhere" business logic layer using WebAssembly (WASM) Component Models, while providing environmental context to the Mecris accountability ecosystem.

## 1. The Core Philosophy: Zero-Split-Brain
The cardinal rule of this architecture is that **Host Environments are ignorant**. The hosts (Go, Python, Kotlin, Spin) do not know how to calculate a moon phase. They do not hold state logic. They only handle I/O (Network, Time, Disk) and pass primitive data to the Brain.

If a bug is found in the lunar calculation, it is fixed in exactly one place: the Rust WASM source. 

## 2. The Components

### 🧠 1. The Oracle (The WASM Brain)
- **Language**: Rust
- **Target**: `wasm32-wasip1` (or Component Model)
- **Function**: Pure, deterministic math. It takes a UNIX timestamp and geographic coordinates (Lat/Lon) as input. It outputs a structured JSON/Record containing:
  - Lunar Phase (New, Waxing Crescent, First Quarter, Waxing Gibbous, Full, Waning Gibbous, Last Quarter, Waning Crescent)
  - Illumination Percentage (0.0 to 1.0)
  - Next Full Moon timestamp
  - **The Torment Multiplier**: A calculated intensity factor (1.0 to 3.0) that peaks during the Full Moon.

### ☁️ 2. The Iron Town Gateway (Spin API Service)
- **Language**: Rust (Fermyon Spin framework)
- **Function**: Serverless cloud gateway. It provides the REST API endpoints (`/api/moon/phase`). It handles the HTTP request, fetches the current system time, calls the WASM Brain, and returns the response.

### 🚜 3. The Reconciler (Kubernetes Controller / Operator)
- **Language**: Go (Kubebuilder)
- **Function**: Watches a Custom Resource Definition (CRD) called `LunarTracker`. It runs a reconciliation loop where it loads the WASM Brain (via `wasmtime-go`), calculates the phase, and writes it back into the CRD's `Status.Conditions`. It allows the Kubernetes cluster to be "aware" of the moon phase for scaling or triggering other cron jobs.

### 💻 4. The Terminal Interface (Go CLI)
- **Language**: Go (Cobra)
- **Function**: A command-line tool (`moonctl`). It embeds the exact same WASM binary. You can run `moonctl phase --time "2026-10-31"` completely offline to query the Oracle locally. 

### 📱 5. The Mobile Scent (Android Client)
- **Language**: Kotlin / Jetpack Compose
- **Function**: A dark-themed widget and dashboard that polls the Spin API (or potentially embeds a Kotlin-Wasmtime runtime). It visualizes the current phase and clearly displays the active "Torment Multiplier."

### 🤖 6. The AI Bridge (Python MCP Server)
- **Language**: Python (FastMCP)
- **Function**: Exposes the `get_lunar_context` tool. When Claude or Gemini are orienting themselves in a Mecris session, they query this MCP. 

## 3. Lore Integration: The Lunar Torment
The Moon Phase Clock is not just an aesthetic toy; it actively influences the severity of the Mecris accountability system.

- **🌑 New Moon (The Silent Forest)**: The system is quiet. The Nag Ladder starts at Tier 1. The Review Pump multiplier is 1.0. Forgiveness is possible.
- **🌓 Waxing (The Building Pressure)**: The ghost archivist becomes more active. The Review Pump multiplier scales up (1.2 - 1.8).
- **🌕 Full Moon (The Boar God's Charge)**: The Torment Multiplier maxes out at 3.0. Any missed Beeminder goals bypass Tier 1 and immediately trigger Tier 3 escalated interventions. The system demands perfection.
- **🌗 Waning (The Receding Tide)**: Pressure slowly releases back to baseline.

## 4. Development Workflow
1. Write and test the Rust math in the `brain/` directory.
2. Compile to `.wasm`.
3. Distribute the `.wasm` binary to the `api/`, `controller/`, and `cli/` directories.
4. Each host implements a minimal wrapper to execute the binary.

---
*Status: Initialized | Architecture: Zero-Split-Brain / Useless*
