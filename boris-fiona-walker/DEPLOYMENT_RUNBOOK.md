# 🚀 Deployment Runbook: Intelligent Context-Aware Reminders (v1)

**Objective**: Deploy the new "Smart Hype-Man" logic to Spin Cloud (WASM) and verify the Local Reasoning Engine (Python).

**Prerequisites**:
- [ ] `spin` CLI installed and authenticated (`spin login`)
- [ ] OpenWeather API Key
- [ ] Beeminder API Key (for user `kingdonb`)

---

## 🏗️ Phase 1: Cloud Deployment (WASM Module)

This deploys the "Fast Reflex" muscle that runs on the cloud.

### 1. Configure Secrets
Set the production variables in Spin Cloud. These allow the WASM module to check the weather and your goal status.

```bash
# Navigate to the module directory
cd boris-fiona-walker

# 1. Weather API (For South Bend checks)
spin cloud variables set openweather_api_key "YOUR_OPENWEATHER_KEY"

# 2. Beeminder Auth (For 'bike' goal checks)
spin cloud variables set beeminder_username "kingdonb"
spin cloud variables set beeminder_api_key "YOUR_BEEMINDER_KEY"

# 3. Location (Defaults to South Bend if skipped, but good to be explicit)
spin cloud variables set latitude "41.6764"
spin cloud variables set longitude "-86.2520"
```

### 2. Deploy
Push the new code to Fermyon Spin.

```bash
spin deploy
```

**Verification**:
- [ ] Deployment command returns a success URL (e.g., `https://boris-fiona-walker-xyz.fermyon.app`)
- [ ] `curl https://boris-fiona-walker-xyz.fermyon.app/health` returns `{"status":"healthy"}`

---

## 🧠 Phase 2: Local Upgrade (Reasoning Engine)

This updates the "Big Brain" on your local machine that provides the deep coaching insights.

### 1. Update Codebase
Ensure you are on the latest `main` branch.

```bash
cd /Users/yebyen/w/mecris
git checkout main
git pull origin main
```

### 2. Restart Server
The Python logic (`mcp_server.py`, `services/coaching_service.py`) is loaded into memory when the process starts.

- If running via `make`: `Ctrl+C` and run `make claude` (or your startup command).
- If running via Claude Desktop: Restart the application.

**Verification**:
- [ ] Ask Claude: *"Status update"*
- [ ] Verify the response includes a specific coaching insight (e.g., *"Since you haven't walked..."* or *"Great job walking..."*) rather than just generic stats.

---

## ✅ Phase 3: Live Verification Checklist

Mark this PR as merged ONLY when these are true:

- [ ] **WASM**: `spin deploy` successful.
- [ ] **WASM Logic**: You received a context-appropriate SMS (or silence) during the 2 PM - 6 PM window.
- [ ] **Python Logic**: `get_coaching_insight` tool call works locally.
