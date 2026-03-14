# Mecris-Go: Technical Architecture & Design

> **Mecris-Go**  
> *Autonomous Intelligence Loop: Health Connect -> Spin -> Mecris -> Multi-Platform Notifications*

## 1. Executive Summary
Mecris-Go is a serverless extension of the Mecris accountability system. It transforms the system from a passive observer into an autonomous agent that proactively detects activity via **Android Health Connect**, manages identity via **Pocket ID (Passkeys)**, and orchestrates reminders via **Fermyon Spin** and **Neon PostgreSQL**.

## 2. Authentication & Security (Pocket ID)
Mecris-Go eliminates passwords in favor of a secure, OIDC-compliant passkey system.

- **Identity Provider**: Pocket ID (Self-hosted/Cloud).
- **Android Integration**: Uses the **Credential Manager API** (Android 14+) for FIDO2/WebAuthn passkey authentication.
- **JWT Validation**: The Spin backend validates incoming JWTs using the Pocket ID JWKS endpoint.
- **Privacy**: Raw GPS traces are processed **on-device** to determine "Walk Events." Only summarized walk metadata (distance, duration, confidence) is sent to the Spin backend.

## 3. Data Architecture (Neon PostgreSQL)
User state and inference history are persisted in a serverless Neon database.

### Schema Overview:
- `users`: `pocket_id_sub`, `beeminder_token_encrypted`, `notification_prefs`, `budget_limit`.
- `walk_inferences`: `user_id`, `start_time`, `end_time`, `confidence_score`, `status` (pending|confirmed|auto-logged).
- `notification_log`: `user_id`, `channel` (Push|Telegram|WhatsApp), `cost_usd`, `sent_at`.

## 4. Spin Module Design (The WASM Backend)
The backend is decomposed into focused WebAssembly modules:

1.  **Auth Service**: Handles Pocket ID JWT validation and session management.
2.  **Sync Service**: Ingests "Walk Events" from the Android app and stores them in Neon.
3.  **Inference Engine (Cron Trigger)**: Runs every 15-30 mins. Reconciles recent Fit data against Beeminder goals.
4.  **Narrator Bridge**: Calls the Mecris MCP `/narrator/context` to fetch current budget and goal urgency.
5.  **Intelligence Service**: Calls LLM (Claude) to draft personalized, budget-conscious reminders.
6.  **Notification Router**: Dispatches messages to FCM (Push), Telegram Bot API, or WhatsApp Business API.

## 5. The Autonomous Intelligence Loop
1.  **Trigger**: Spin Cron task activates.
2.  **Context Assembly**: Spin pulls user data from Neon + Beeminder status + Mecris budget status.
3.  **Decision**: 
    - *Scenario*: User hasn't walked, Beeminder derails in 4 hours, Budget has $10. 
    - *Action*: Prompt Claude for a "Sassy Saturday" reminder.
4.  **Dispatch**: Send "Walk the dogs!" notification via the user's preferred channel.
5.  **Auto-Log**: If Health Connect data confirms a walk later, the **Beeminder Bridge** automatically logs the data point.

## 6. Android App Architecture
- **Framework**: Jetpack Compose.
- **Health Integration**: Health Connect SDK.
- **Background Work**: `WorkManager` for periodic Health Connect polling and local GPS processing.
- **Auth**: Credential Manager for Passkey support.

## 7. Mecris Integration Strategy (Hybrid)
Mecris remains the **Source of Truth** for:
- **Unified Context**: The `/narrator/context` endpoint.
- **Budget Tracking**: Managing the Claude/Groq usage limits.
- **Spin Interface**: Spin acts as the autonomous "operator" that queries the Mecris MCP to drive real-world actions.

---
*This architecture ensures that Mecris-Go is secure, privacy-preserving, and truly autonomous.*