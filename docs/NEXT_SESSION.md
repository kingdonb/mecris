# Next Session Plan - 2026-03-21

## ✅ Completed in Last Session
- **Android Persistence**: Caching layer implemented via `PersistenceManager` to smooth startup.
- **Robust Scraper**: Cloud failover scraper now handles redirects and enriched forecast data.
- **Health Visibility**: "HOME: ONLINE" vs "CLOUD: FAILOVER" status now live in UI.
- **Urgency Cues**: Refined prominence logic for tomorrow's and 7-day language goals.

## 🚀 Immediate Next Steps

### 1. 🧹 Workspace Cleanup (Issue #104)
- **Model Relocation**: Move the 9GB of model files in `tools/` to a gitignored `.models/` directory or external storage.
- **Setup Script**: Create `scripts/setup_models.sh` to download/symlink these models on demand.
- **Searchability**: Once moved, verify that `grep -r` is fast and reliable across the whole repo.

### 2. 🌀 Coordination Finalization (Issue #100)
- **Cron Activation**: Re-enable the Cron trigger in `spin.toml` once the local MCP leader can coordinate cloud events.
- **Leadership Check**: Ensure the local leader proactively pulses the heartbeat to avoid unnecessary failovers.

### 3. 📱 Android Diagnostics
- **Data Quality**: Expand the "Data Quality Diagnostics" to show more detail about Beeminder vs Local vs Cloud sync discrepancies.
- **Cache invalidation**: Add a way to manually clear the local cache from the "Settings" menu.

## 📝 Mecris Note
The system is now remarkably stable in its "dual-brain" (Python + Spin) configuration. The next leap is ensuring they stay in perfect sync without manual pulses.
