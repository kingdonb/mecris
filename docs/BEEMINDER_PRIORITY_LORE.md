# Beeminder Priority Lore: Architectural Impressions

## Core Philosophy: The Multi-Tiered Priority Queue
Beeminder's background worker system (documented at `doc.beeminder.com/priority`) is a masterclass in balancing **snappiness** (user-facing responsiveness) with **throughput** (massive background data processing). It uses a 5-tier hierarchical queue system:

1.  **SNAPPY:** Immediate, user-waiting tasks (e.g., clicking "Sync" in the app).
2.  **LOCKSY:** Critical but background-safe (e.g., goal state updates).
3.  **BATCHY:** Regular maintenance (e.g., fetching 100 auto-sync goals).
4.  **WHALEY:** Resource-heavy, slow processing (e.g., historical re-imports).
5.  **UNDULY:** Low-priority "whenever" tasks.

## 🧠 Algorithmic Lessons for Mecris
- **Worker Fallback:** A worker doesn't just "do one job." It checks the queues in order. It only works on BATCHY if SNAPPY and LOCKSY are empty. This prevents low-priority "whales" from starving high-priority "snaps."
- **Adaptive Frequency:** We should apply this to our walk and budget checks. If a walk is "Required" or "Critical," we should check Health Connect more frequently (SNAPPY/LOCKSY). If it's "Completed," we back off to a lower tier (BATCHY/UNDULY) to save battery and compute.
- **Explicit Serialization:** Using LOCKSY for database writes ensures that even if we scale horizontally (multiple MCP server instances or multiple phone syncs), we maintain data integrity without blocking the user interface.

## 🐾 Mecris Implementation Status
- **Current Sync:** Our 15-minute cooldown implementation is a step toward this. It moves from "Aggressive Spamming" to a "Scheduled Batch" model.
- **Future Goal:** Implement a `PriorityScanner` that increases polling frequency as the Beeminder deadline approaches, mirroring the Beeminder Android app's behavior.
