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
  - `users`: `pocket_id_sub` (PK), `beeminder_token_encrypted`, `notification_prefs`, `timezone`, `budget_limit`, `budget_spent_groq` (Source of truth for LLM spend), `mcp_server_url`.
  - `walk_inferences`: `id`, `user_id`, `start_time`, `end_time`, `distance_meters`, `confidence_score`, `status` (pending | confirmed | rejected | auto-logged), `created_at`.
    - *Idempotency Constraint*: `UNIQUE INDEX idx_walk_user_start ON walk_inferences(user_id, start_time);` (prevents double-logging if Android syncs twice).
  - `notification_log`: `id`, `user_id`, `channel` (Push | Telegram | WhatsApp), `cost_usd`, `prompt_tokens`, `completion_tokens`, `sent_at`.
    - *Spam Prevention Constraint*: `CHECK (sent_at > NOW() - INTERVAL '4 hours')` logic in Spin to prevent duplicate reminders in the same window.

## 4. Android App Architecture & Health Connect
- **Framework**: Jetpack Compose with modern Material 3 design.
- **Health Integration**: Android Health Connect SDK.
- **Background Work & Limits**: Health Connect restricts background reads. We use `WorkManager` (runs every ~15-30 mins when constraints like battery/network are met) to fetch newly aggregated Step, Distance, and Exercise Route records. 
- **Local Heuristics Engine**: The app evaluates the raw data:
    - *Rule MVP*: If `Steps > 2000` AND `Time > 20 min` AND `GPS variance implies outdoor movement` -> Confidence 90%.
    - If confidence > 70%, it queues an HTTP POST to the Spin Sync Service. (If sync fails, WorkManager applies exponential backoff).

## 5. Spin Module Design (The WASM Backend)
The backend is decomposed into focused WebAssembly modules (Rust or Go):

1.  **Auth Service**: Middleware that intercepts requests, validates Pocket ID JWTs, and injects user context.
2.  **Sync Service**: Ingests "Walk Events" from the Android app. Handles deduplication using the `idx_walk_user_start` unique constraint.
3.  **Cron Trigger (The Operator)**: 
    - Fermyon Spin uses a global cron, not per-user. 
    - Implementation: Runs every 15 minutes globally (`0 */15 * * * *`). It queries Neon for users in specific timezones whose `next_check_at <= NOW()`, and dispatches internal jobs/events for those users.
4.  **Mecris Bridge / Edge Agent**: A client that fetches current budget, Beeminder runways, and system state. 
    - *Phase 1-3 Implementation*: Spin acts as an HTTP client calling the existing centralized/home-hosted Mecris API via a secure tunnel.
    - *Phase 4 Long-term vision*: Mecris logic ports to user-owned Spin modules or an Android Edge AI, allowing the device itself to make API calls using its decrypted data.
5.  **Intelligence Service**: Evaluates Mecris context. If action is needed, invokes an LLM to draft personalized, context-aware reminders. To maintain aggressive cost-consciousness, this relies on **Groq via Noclod** (e.g., using Llama 3 or Mixtral). After the call, Spin increments `users.budget_spent_groq` in Neon.
6.  **Notification Router**: Dispatches drafted messages. Evaluates user preference hierarchy. **WhatsApp Business API (via Twilio)** is the primary, production-ready channel utilizing pre-approved marketing/utility templates. 

## 6. The Autonomous Intelligence Loop
This is the core value proposition of Mecris-Go.

1.  **Trigger**: Spin Global Cron task activates, identifies that it's 4:00 PM for User A based on `users.timezone`.
2.  **Context Assembly**: Spin pulls Beeminder status + Mecris budget status (`budget_spent_groq` vs `budget_limit`).
3.  **Decision & Budget Check**: 
    - *Scenario*: User hasn't walked, Beeminder derails in 4 hours.
    - *Conflict Resolution Check*: If Beeminder already shows "completed" manually today, abort.
    - *Action*: Prompt Groq (via Noclod) to fill in the variables for a "Sassy Saturday" reminder.
4.  **Dispatch (WhatsApp Templates)**: 
    - Spin uses a pre-approved Twilio template, for example:
      - *Template*: `mecris_reminder_v1`
      - *Body*: `👋 {{1}}\n\n{{2}}\n\nReply YES to confirm.`
      - *Groq Provides*: `1="Walk time!"`, `2="Your 'dog walk' goal derails in 4 hours. Last walk: yesterday."`
    - Spin sends the formatted payload via Twilio API.
5.  **Auto-Log Closure**: Once the user actually walks, Android `WorkManager` syncs the walk to Spin. Spin inserts it into Neon, calls the Beeminder API to log the datapoint, and sends a final congratulatory ping. Beeminder API calls rely on the unique request ID/timestamp to handle idempotency.

## 7. Implementation Roadmap
- **Phase 1 (MVP)**: Android app with Health Connect OAuth, local WorkManager heuristics, manual confirmation button, and direct Beeminder API sync.
- **Phase 2 (Cloud State)**: Introduce Pocket ID, Fermyon Spin sync service, and Neon DB to securely store inferences. Spin connects via HTTP to external Mecris MCP.
- **Phase 3 (WhatsApp & Noclod)**: Introduce the Spin Global Cron Trigger (with timezone handling), Twilio WhatsApp integration (using existing approved templates), and Groq/Noclod LLM integration with Neon-backed budget tracking.
- **Phase 4 (Decentralized Mecris)**: Port the core `/narrator/context` Mecris logic into individual user-owned Spin modules or directly onto the Android edge device.