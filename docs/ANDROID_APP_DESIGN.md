# Mecris-Go: Technical Architecture & Design

> **Mecris-Go**  
> *Autonomous Intelligence Loop: Health Connect -> Spin -> Mecris -> Multi-Platform Notifications*

## 1. Executive Summary
Mecris-Go is a serverless extension of the Mecris accountability system. It transforms the system from a passive observer into an autonomous agent that proactively detects activity via **Android Health Connect**, manages identity via **Pocket ID (Passkeys)**, and orchestrates reminders via **Fermyon Spin** and **Neon PostgreSQL**. 

It prioritizes privacy (on-device processing) and cost-consciousness (budget-aware LLM execution).

## 2. Authentication & Security (Pocket ID)
Mecris-Go eliminates passwords in favor of a secure, OIDC-compliant passkey system.

- **Identity Provider**: Pocket ID (Self-hosted or Cloud).
- **Android Integration**: Uses the **Credential Manager API** (Android 14+) for FIDO2/WebAuthn passkey authentication.
- **JWT Validation**: The Spin backend validates incoming JWTs using the Pocket ID JWKS endpoint.
- **Privacy by Design**: Raw GPS traces (Exercise Routes) are processed **strictly on-device**. Only summarized walk metadata (distance, duration, confidence score) is sent to the Spin backend. Location data never leaves the phone.

## 3. Data Architecture (Neon PostgreSQL)
User state, preferences, and inference history are persisted in a serverless Neon database. 

- **Connection Management**: Because Spin modules scale down to zero and instantiate rapidly, we must use a connection pooler (like **pgBouncer** or Neon's built-in pooler) to prevent connection exhaustion.
- **Schema Overview**:
  - `users`: `pocket_id_sub` (PK), `beeminder_token_encrypted`, `notification_prefs`, `budget_limit`, `mcp_server_url`.
  - `walk_inferences`: `id`, `user_id`, `start_time`, `end_time`, `distance_meters`, `confidence_score`, `status` (pending | confirmed | rejected | auto-logged), `created_at`.
  - `notification_log`: `id`, `user_id`, `channel` (Push | Telegram | WhatsApp), `cost_usd`, `prompt_tokens`, `completion_tokens`, `sent_at`.

## 4. Android App Architecture & Health Connect
- **Framework**: Jetpack Compose with modern Material 3 design.
- **Health Integration**: Android Health Connect SDK.
- **Background Work & Limits**: Health Connect restricts background reads. We use `WorkManager` (runs every ~15-30 mins when constraints like battery/network are met) to fetch newly aggregated Step, Distance, and Exercise Route records. 
- **Local Heuristics Engine**: The app evaluates the raw data:
    - *Rule MVP*: If `Steps > 2000` AND `Time > 20 min` AND `GPS variance implies outdoor movement` -> Confidence 90%.
    - If confidence > 70%, it queues an HTTP POST to the Spin Sync Service.

## 5. Spin Module Design (The WASM Backend)
The backend is decomposed into focused WebAssembly modules (Rust or Go):

1.  **Auth Service**: Middleware that intercepts requests, validates Pocket ID JWTs, and injects user context.
2.  **Sync Service**: Ingests "Walk Events" from the Android app. Handles deduplication/idempotency (e.g., ignoring duplicate syncs of the same time window).
3.  **Cron Trigger (The Operator)**: Runs periodically. It orchestrates the flow below.
4.  **Mecris Bridge**: A client that calls the existing Mecris MCP `/narrator/context` to fetch current budget, Beeminder runways, and system state.
5.  **Intelligence Service**: Evaluates Mecris context. If action is needed, invokes Anthropic (Claude API) to draft personalized, context-aware, and budget-conscious reminders.
6.  **Notification Router**: Dispatches drafted messages. Evaluates user preference hierarchy (e.g., Try Telegram -> Fallback to Android FCM Push -> Fallback to SMS).

## 6. The Autonomous Intelligence Loop
This is the core value proposition of Mecris-Go.

1.  **Trigger**: Spin Cron task activates (e.g., 4:00 PM local time).
2.  **Context Assembly**: Spin pulls Beeminder status + Mecris budget status (`$21.00 left`).
3.  **Decision & Budget Check**: 
    - *Scenario*: User hasn't walked, Beeminder derails in 4 hours, Budget is healthy.
    - *Conflict Resolution Check*: If Beeminder already shows "completed" manually today, abort.
    - *Action*: Prompt Claude (Sonnet 3.5) for a "Sassy Saturday" reminder. If budget was low (<$2.00), downgrade to Haiku.
4.  **Dispatch**: Send "Walk the dogs!" notification.
5.  **Auto-Log Closure**: Once the user actually walks, Android `WorkManager` syncs the walk to Spin. Spin updates the database, calls the Beeminder API to insert the datapoint, and sends a final congratulatory ping: *"Walk detected and logged. Buffer extended."*

## 7. Implementation Roadmap
- **Phase 1 (MVP)**: Android app with Health Connect OAuth, local WorkManager heuristics, manual confirmation button, and direct Beeminder API sync (no LLM, no Spin).
- **Phase 2 (Cloud State)**: Introduce Pocket ID, Fermyon Spin sync service, and Neon DB to securely store inferences.
- **Phase 3 (Autonomous Loop)**: Introduce the Spin Cron Trigger, Mecris MCP Bridge, Anthropic LLM integration, and Telegram notifications.
- **Phase 4 (Advanced Platforms)**: Add WhatsApp Business API support and Android FCM Push Notifications.
