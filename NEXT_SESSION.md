# Next Session: Kubernetes Tailnet Hosting & Local AI Exploration

## Context
- **Last Session**: Antigravity CLI MCP server integration and secure `.env` absolute-path loading completed.
- **Current State**:
  - Global `mcp_config.json` configured cleanly in `~/.gemini/antigravity-cli/mcp_config.json` with no hardcoded credentials.
  - `mcp_server.py` loads `.env` dynamically from its own directory path, keeping secrets safely isolated.
  - Android "Cloud Sync" verified functional (syncing walks and language stats).
  - Walk today of 0.60 miles completed and registered.

## High Priority
1. **Kubernetes Tailnet Deployment Planning**:
   - Explore permanent hosting of the Mecris deployment (sync-service, database link, scheduler daemon) on the user's new HA 9-node Tailnet Kubernetes cluster.
   - Investigate deploying the sync-service as a native Kubernetes deployment or containerized pod.
2. **Local AI Model Execution via Hailo AI**:
   - Investigate loading low-footprint local models on the cluster's Hailo AI accelerator.
   - Document how Mecris could interface with local inference endpoints to offload agent tasks.
3. **Tab Maestro Analysis**:
   - Investigate why Tab Maestro could fit where other tools struggled, and understand key integration pathways.
4. **Fix Fermyon/Spin Integration**:
   - Restore the `/internal/review-pump-status-py` cloud endpoint and address Spin CLI 4.0 issues.
5. **Review Pump & Streaming API Audit**:
   - Audit target calculation logic (why Greek pins at 100).
   - Integrate streaming token visualization in the Python harness.

## Notes for the Narrator
- The user is preparing for a livestream. Secrets are successfully scrubbed from public config fields. Keep any logs and visual displays completely clean.
- The 9-node K8s HA cluster with Hailo AI accelerator is the next core hosting target.
- Walk status is updated and active! Keep motivation high.
