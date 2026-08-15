---
name: chore-web-inventory
description: 'Weekend chore 5-minute guided walkthrough and inventory for the Mecris Web app (React/Vite SPA on http://localhost:5173, PocketID OIDC, Multi-Cloud degradation, and interactive dashboard). Trigger with /chore-web-inventory'
allowed-tools: ['run_command', 'view_file', 'grep_search', 'list_dir', 'call_mcp_tool']
---

# Weekend Chore: Web App Interactive Walkthrough & Play-Test

Part of the **Weekend Chores** accountability workflow. This skill guides the **human operator** and AI assistant together through a 5-minute visual and functional check of the Mecris Web frontend.

## The Weekend Chores Philosophy: Human-in-the-Loop

- **Role of the Agent**: Co-pilot and diagnostic guide. The agent prepares the environment, runs background health checks, and highlights discrepancies.
- **Role of the Human**: The human completes the chore by visually inspecting the dashboard, logging in via PocketID, and verifying the state of their personal accountability system.
- **Frequency**: Done **both Saturday and Sunday** to count as completed. On Sunday's run, a lookback flair is recorded.

---

## 5-Minute Guided Chore Routine

### Step 1: Spin up the Local Dev Server
```bash
cd /Users/yebyen/w/mecris/web
npm run dev
```
- Server starts at: **`http://localhost:5173/`**

### Step 2: Human Visual & Interactive Inspection (The Chore)
Open **`http://localhost:5173/`** in your browser and verify:
1. **PocketID Neural Link Login**: Click **CONNECT TO NEURAL LINK** and complete the OIDC check-in with `metnoom.urmanac.com`.
2. **Provider Badge**: Check which backend is active (`HOME`, `AKAMAI`, or `FERMYON`).
3. **System Pulse Matrix**: Verify the status LEDs for `MCP SERVER`, `AKAMAI FUNCTIONS`, and `ANDROID CLIENT`.
4. **Momentum & The Majesty Cake**: Look at the current goal completion score (e.g., `0/3` vs `3/3` cake).
5. **Language Liabilities (The Review Pump)**: Check the daily clearance targets for Arabic and Greek, and adjust multipliers if necessary.
6. **Odometers**: Verify the Virtual Budget ($) and Today's Walk Distance (MI).

### Step 3: Fast Technical Verification (Automated Baseline)
```bash
cd /Users/yebyen/w/mecris/web
npm test
npm run build
```

---

## Architecture Reference

```
                      +-----------------------------+
                      |   PocketID OIDC (Home VPN)  |
                      |  https://metnoom.urmanac.com |
                      +--------------+--------------+
                                     |
                                 Auth Tokens
                                     v
+------------------+     +-----------------------+     +-------------------+
|  Android Client  | --> |  Mecris Web Frontend  | <-- |   Local MCP /     |
| (Health Connect) |     |  (React 19 + Vite)    |     | Akamai / Fermyon  |
+------------------+     +-----------+-----------+     +-------------------+
                                     |
                 Graceful Multi-Backend Degradation
                                     |
         +---------------------------+---------------------------+
         |                                                       |
         v                                                       v
+-------------------------------+              +-----------------------------------+
| 1. Fermyon Cloud (Spin)       |              | 2. Akamai Functions (Edge)        |
|    (Legacy / Failover Primary)|              |    (Active Primary Backend)       |
+-------------------------------+              +-----------------------------------+
         |                                                       |
         +---------------------------+---------------------------+
                                     | (if cloud offline)
                                     v
                       +---------------------------+
                       | 3. Local Python MCP Server|
                       |    (FastAPI on Port 8080) |
                       +---------------------------+
```
