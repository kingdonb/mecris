# Feature: Neural Link (Web UI)

The **Neural Link** is a thin-client Web UI for the Mecris system, designed to provide high-fidelity observability and administrative control from any browser. It bridges the gap between local home mode and remote cloud mode, especially during off-VPN travel.

## 1. User Stories

- **US-01**: As a user, I want to see my daily status (Majesty Cake) in a web browser so that I can track my progress without opening the Android app.
- **US-02**: As a user, I want to see the heartbeat status of all system modalities (Android, Local Python, Cloud Cron) so that I know if my system is synchronized and healthy.
- **US-03**: As a user, I want the Web UI to automatically discover and prefer my local home server when I am on my home network, falling back to the Cloud API otherwise.
- **US-04**: As an administrator, I want to adjust language review pump multipliers directly from the Web UI to manage my daily liabilities.
- **US-05**: As a user, I want a secure login flow using my PocketID credentials so that my personal data remains private.

## 2. Functional Requirements

- **FR-01: Authentication**
  - Integrate with PocketID OIDC provider.
  - Support token persistence in `localStorage`.
  - Display "INITIATING NEURAL LINK..." during authentication.
- **FR-02: Dashboard Visualization**
  - Implement **Momentum Visualizer** (pulsing CSS/SVG).
  - Implement **Odometer** views for virtual budget and daily distance.
  - Replicate the **Majesty Cake** daily aggregate status.
  - Support the **Review Pump** lever controls for Arabic and Greek.
- **FR-03: System Pulse (Observability)**
  - Display a "System Pulse" panel showing active modalities.
  - Use traffic-light color coding (Green/Yellow/Red) based on heartbeat age.
  - **Local Python**: Green < 90s, Yellow < 5m, Red > 5m.
  - **Android**: Green < 20m, Yellow < 1h, Red > 4h.
  - **Cloud Cron**: Green < 2h 10m (for reminders), Red > 4h.
- **FR-04: API Integration**
  - Use `GET /aggregate-status?full=true` to fetch consolidated goal and pulse data.
  - Handle CORS preflight (`OPTIONS`) and headers for all backend requests.
- **FR-05: Local Discovery**
  - Probing logic for `http://localhost:8000`.
  - Fallback to configured Cloud API (Akamai/Fermyon) if local probe fails.
- **FR-06: Cloud Heartbeats**
  - Modify backend cron jobs to post heartbeats to `scheduler_election`.

## 3. Success Criteria

- **SC-01**: User can log in with PocketID and see their real daily step count and language stats.
- **SC-02**: System Pulse accurately reflects if the Android app hasn't heartbeated in 4+ hours (Red light).
- **SC-03**: Local mode activates automatically when the user is running the local MCP server with the HTTP bridge.
- **SC-04**: Changing a multiplier in the Web UI persists the change in the Neon DB.

## 4. Edge Cases & Constraints

- **EC-01: Token Expiry**: UI must redirect to login or show "LINK FAILURE" when the OIDC token expires.
- **EC-02: Split Horizon Networking**: UI must handle cases where `metnoom.urmanac.com` is reachable but `localhost:8000` is not (and vice-versa).
- **EC-03: Multiple Cloud Locations**: UI should report which cloud endpoint (Akamai vs Fermyon) it is currently talking to.
- **Constraint**: No background workers or indexing allowed in the browser environment.
