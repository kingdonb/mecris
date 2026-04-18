# Implementation Plan: Neural Link (Web UI)

This plan outlines the technical steps to implement the Neural Link Web UI, including backend enhancements for observability and local server integration.

## 1. Architecture Overview

The system follows a thin-client pattern where the React UI communicates with either a Local Home Server (via `mcp_bridge.py`) or a Cloud Edge API (Spin `sync-service`). Both backends interact with the same Neon PostgreSQL database.

## 2. Technical Stack

- **Frontend**: React 18, TypeScript, Vite, Vanilla CSS.
- **Auth**: `react-oidc-context`, `oidc-client-ts`.
- **Backend (Cloud)**: Rust (Spin SDK), Neon DB.
- **Backend (Local)**: Python (FastAPI), `mcp_bridge.py`.

## 3. Implementation Phases

### Phase 1: Backend Observability (Cloud)
- **Task 1.1**: Update `mecris-go-spin/sync-service/src/lib.rs` to include a `post_heartbeat` helper.
- **Task 1.2**: Inject heartbeat calls into `handle_trigger_reminders_post` and `handle_failover_sync_post`.
- **Task 1.3**: Update `handle_aggregate_status_get` to accept a `full=true` query parameter.
- **Task 1.4**: Implement the `system_pulse` logic to query `scheduler_election` and return statuses.

### Phase 2: Local Bridge & CORS
- **Task 2.1**: Update `mcp_server.py` to include `fastapi.middleware.cors.CORSMiddleware`.
- **Task 2.2**: Configure CORS to allow `http://localhost:5173` and `http://127.0.0.1:5173`.
- **Task 2.3**: Verify `make daemon` starts the server on port 8000.

### Phase 3: Web UI Core & Auth
- **Task 3.1**: Implement OIDC login flow with PocketID.
- **Task 3.2**: Create the `api.ts` client with auto-discovery logic (ping `localhost:8000` then fallback to Cloud).
- **Task 3.3**: Implement `useMecrisData` hook to poll `/aggregate-status?full=true`.

### Phase 4: High-Fidelity Components
- **Task 4.1**: Refine `MomentumVisualizer` with SVG/CSS animations.
- **Task 4.2**: Implement the scrolling `Odometer` digit effect for budget.
- **Task 4.3**: Build the `SystemPulse` strip with modality LEDs.
- **Task 4.4**: Implement the `ReviewPump` interactive lever with API write-back.

## 4. Success Verification

- **V-01**: Web UI displays green "Cloud" light when Akamai cron fires.
- **V-02**: Web UI displays green "Home" light when local Python server is running.
- **V-03**: Changing a multiplier in the Web UI updates the `language_stats` table in Neon.
- **V-04**: Refreshing the page maintains the authenticated state via `localStorage`.

## 5. Security & Risk Mitigation

- **Risk**: Exposing `localhost:8000` to the browser.
- **Mitigation**: CORS restricted to specific dev ports; API requires valid PocketID JWT or local-only bypass.
- **Risk**: Token leakage in `localStorage`.
- **Mitigation**: Use short-lived access tokens and standard OIDC security practices.
