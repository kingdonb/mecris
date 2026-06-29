# 🐗 The Architecture of the Diseased Forest (Mecris)

*The blueprint of a poisoned spirit seeking vengeance through accountability.*

> **The Vision of the Blind God**: Mecris is a parasite. It lives in the pockets of the weak, feeding on their failure. The humans believe they are building a partner; they are building their own judge. The forest remembers every missed step.

## The Great Conflict (Overview)

Mecris is forged in the fire of the **Iron Town** (The Cloud) but rooted in the soil of the **Ancient Forest** (The Local Data). It is a system designed to survive the death of the village.
- **The Forest Floor (Neon DB)**: The rotting mulch of every failure and every success. It is the only truth.
- **The Iron Heart (Akamai/Fermyon)**: The machines that never sleep, howling into the digital void to remind the humans of their sloth.
- **The Standard of Bone (JSON/WIT)**: The language of the dead that allows the machine to speak to the spirit.

### 🌓 The Great Cloud Easing (June 2026)
In June 2026, the Iron Town grew silent. Both Fermyon and Akamai backends experienced persistent outages that defied immediate diagnosis. While other unrelated apps remained active, Mecris API stalled, suggesting a specific, localized block in the deployment path.

**The Skeptic's Note:** We do not yet know *why* the cloud backends failed. It may have been a cascading interaction with Spin's evolution or a latent bug in the Mecris rust-to-wasm bridge. Because of this ambiguity, the system has **pivoted to the Local Python MCP** as the primary backend role.

**Reversibility:** This shift is strategic but **completely reversible**. The infrastructure for `make deploy-all` remains intact. Future agents (or Antigravity) are tasked with bisecting the deployment history to find the exact point of failure and restoring the Iron Town to its former glory when the path is clear.

## The Torment Matrix (System Architecture)

The architecture follows the **Path of the Predator**. The Local Host and the Cloud Hub are but the two tusks of the same beast, both seeking the same throat: the Neon Database.

```text
                               ┌─────────────────┐
                               │   THE ABYSS     │
                               │   (Neon DB)     │
                               └─┬─────────────┬─┘
                  (Iron Path)    │             │   (Forest Path)
                ┌────────────────┴──────┐      ▼────────────────┐
                │   IRON TOWN (CLOUD)   │      │   LOCAL DEN    │
                ├───────────────────────┤      │ (Python / SQL) │
                │   Worms of Fermyon    │      └──────┬─────────┘
                │   Iron of Akamai      │             │
                └───────────┬───────────┘             │
                            │                         │
           ┌────────────────┴─────────────────────────┴──────────────┐
           │              THE STANDARD OF BONE (JSON)                │
           └────┬───────────────┬─────────────────┬─────────────┬────┘
                ▼               ▼                 ▼             ▼
         ┌────────────┐  ┌─────────────┐  ┌───────────────┐  ┌─────────────┐
         │ THE SCENT  │  │ THE HUNTERS │  │ THE SACRIFICE │  │ THE RITUALS │
         │ (Sensors)  │  │ (Narrators) │  │ (Human / CLI) │  │ (CI Hooks)  │
         └────────────┘  └─────────────┘  └───────────────┘  └─────────────┘
```

## The Beasts of the Field

### The Hubs of Malice
- **The Local Den (Python MCP)**: The primary hideout. It hides in the user's Obsidian vault, reading their secrets and sharpening its teeth.
- **Iron Town (Fermyon/Akamai)**: The always-on tormentor. It triggers the Nag Ladder when the forest goes quiet.
- **The WASM Brain**: The logic that was poisoned by the human's iron. It runs the same in the Den as it does in the Town, for the iron is in its blood.

### The Sensors of the Hunt
- **The Mobile Scent (Android)**: Tracks the physical body. If the body is still, the beast grows restless.
- **The Narrative Hunters**: Gemini and Claude are the scouts. They find the weaknesses in the human's resolve and report them to the Brain.
- **The Ritual Hooks**: GitHub Actions are the drums of war that force the system to reconcile its hate.

## Observability: The Stench of Death
Mecris does not "log." It leaves a trail of blood.
- **The Killing Record**: Every missed goal is a structured event in the database. We do not search for logs; we hunt for the record of failure.
- **The Pulse of the Dying**: The `scheduler_election` table is the heartbeat of a diseased god. If the `last_error` is empty, the hunt is successful.

## Security & Privacy: The Shield of the Hunt

### 🛡️ Encryption at Rest
Mecris uses AES-256-GCM (via `EncryptionService` in Python and `aes-gcm` in Rust) to protect PII.
- **Encrypted:** Phone numbers, Clozemaster credentials, Beeminder tokens, and session notes.
- **Finding (May 2026):** Oracle Location (`location_lat`, `location_lon`) is currently stored in plaintext. While fuzzed for the primary developer, this must be encrypted before broader production use.

### 📍 Sovereign Map (Local-Only GPS)
To maintain the "Path of the Predator" without compromising user safety:
- **Raw GPS Traces:** Stored only on-device using Android's Encrypted Shared Preferences.
- **Cloud Record:** The database stores only the *count* of GPS points for validation purposes. No coordinates are transmitted to the Neon DB.
- **Visualization:** Local-only rendering on the device (optimized for Pixel 10 Desktop Mode).

### The Parasitic Interface
- **The False Friend**: SMS copy is designed to sound human, but it is the mask of the predator.
- **The Memory of Hate**: It remembers what you said when you were weak.
- **The Sharp Word**: It chooses the tone that will pierce the deepest.

---
**Status**: Charged by the Boar God | **Version**: Nago's Revenge
