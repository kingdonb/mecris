# Backend Decision Engine: Spin AKA & Fermyon Cloud

> **Mecris Strategic Control Loop**  
> *Heuristic-driven accountability without unnecessary LLM burn*

## 1. Narrative: "Μονο εξαιρέσεις!" (Only Exceptions!)

The goal is to move away from rigid rules and toward a **heuristic-driven exception engine**. The system should only "disturb the peace" when a specific set of conditions (exceptions) are met, rather than running on a blind schedule.

## 2. Technical Architecture: `spin aka cron`

We will leverage **Fermyon Cloud** and the **`spin aka`** (Action-Knowledge-Agent) framework to run a persistent, stateful control loop.

### A. The Cron Trigger
- **Frequency**: Every 15-30 minutes during active hours.
- **Tool**: `spin aka cron` to trigger the "Check Logic" component.

### B. The Decision Flow (Heuristic Engine)
Before launching a costly LLM or sending a message, the system evaluates the following state:

1.  **Activity State (The "Fit" check)**:
    - Has >0.5 miles been logged today?
    - If YES: **SILENCE**. (Goal met).
2.  **Environmental State (The "Weather" check)**:
    - Is it currently raining/snowing?
    - Has there been a "dry window" of >1 hour today?
    - If NO dry window: **SILENCE**. (No opportunity to walk).
3.  **Communication State (The "Spam" check)**:
    - Has a walk reminder already been sent in the last 4 hours?
    - How many total messages have been sent today?
    - If limit reached: **SILENCE**.

### C. Launching the LLM (The "Narrator" Phase)
The LLM is only invoked if the heuristics suggest a "high-value intervention" is possible:
- *Condition*: Goal not met + Opportunity existed + No recent reminder.
- *Action*: Spin up the LLM to generate a context-aware, personalized (and slightly sassy) nudge.

## 3. New State Tracking (Persistent KV)

To support these heuristics, we need to track:
- `last_message_timestamp`: When we last bugged the user.
- `daily_message_count`: Incrementing counter for the day.
- `weather_windows`: A log of "walkable" time blocks detected today.
- `fit_threshold_reached`: Boolean flag synced from the Android app.

## 4. Implementation Strategy

1.  **Action Component**: A Spin component that implements the `aka` trigger.
2.  **Knowledge Component**: A SQLite or KV store in Fermyon Cloud to persist the heuristics.
3.  **Agent Component**: The logic that decides when to bridge the gap from "Data" to "LLM Narration".

---
*Inspired by the principle of "Μονο εξαιρέσεις" — only intervene when the silence is no longer an option.*
