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
4.  **Mecris Bridge / Edge Agent**: A client that fetches current budget, Beeminder runways, and system state. *Long-term vision:* Mecris itself will not be a centralized server, but rather a decentralized, serverless entity. It will likely run as an independent Spin module per user, or even directly on the user's Android device (Edge AI). This ensures that when a user decrypts their data, the API calls originate from them directly.
5.  **Intelligence Service**: Evaluates Mecris context. If action is needed, invokes an LLM to draft personalized, context-aware reminders. To maintain aggressive cost-consciousness, this relies on **Groq via Noclod** (e.g., using models like Llama 3 or Mixtral), completely bypassing expensive APIs like Anthropic.
6.  **Notification Router**: Dispatches drafted messages. Evaluates user preference hierarchy. **WhatsApp Business API (via Twilio)** is the primary, production-ready channel utilizing pre-approved marketing/utility templates. (Telegram is relegated to a future nice-to-have, and FCM Push remains the fallback).

## 6. The Autonomous Intelligence Loop
This is the core value proposition of Mecris-Go.

1.  **Trigger**: Spin Cron task activates (e.g., 4:00 PM local time).
2.  **Context Assembly**: Spin pulls Beeminder status + Mecris budget status (`$1.34` Groq usage this month).
3.  **Decision & Budget Check**: 
    - *Scenario*: User hasn't walked, Beeminder derails in 4 hours.
    - *Conflict Resolution Check*: If Beeminder already shows "completed" manually today, abort.
    - *Action*: Prompt Groq (via Noclod) for a "Sassy Saturday" reminder using pre-approved Twilio WhatsApp templates.
4.  **Dispatch**: Send "Walk the dogs!" notification via WhatsApp.
5.  **Auto-Log Closure**: Once the user actually walks, Android `WorkManager` syncs the walk to Spin. Spin updates the database, calls the Beeminder API to insert the datapoint, and sends a final congratulatory ping: *"Walk detected and logged. Buffer extended."*

## 7. Implementation Roadmap
- **Phase 1 (MVP)**: Android app with Health Connect OAuth, local WorkManager heuristics, manual confirmation button, and direct Beeminder API sync.
- **Phase 2 (Cloud State)**: Introduce Pocket ID, Fermyon Spin sync service, and Neon DB to securely store inferences.
- **Phase 3 (WhatsApp & Noclod)**: Introduce the Spin Cron Trigger, Twilio WhatsApp integration (using existing approved templates), and Groq/Noclod LLM integration.
- **Phase 4 (Decentralized Mecris)**: Port the core `/narrator/context` Mecris logic into individual user-owned Spin modules or directly onto the Android edge device.
