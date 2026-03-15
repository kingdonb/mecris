# 📊 Reviewstack Expansion & API Stewardship Plan

## 1. Current State Assessment (March 15, 2026)
- **Scraper Status:** `scripts/clozemaster_scraper.py` is fully functional and extracts data for both Arabic (`ara-eng`) and Greek (`ell-eng`).
- **Integration:** The data is visible in the Android app (Mecris-Go) and available via the MCP `get_language_velocity_stats` tool.
- **Automation Status:** **Inactive.** Data is currently fetched on-demand (e.g., when the Android app syncs or the MCP tool is called). There are **no** active cron jobs or background workers pushing data to Beeminder automatically.
- **Beeminder Stewardship:** We are currently respecting the "family business" nature of Beeminder by avoiding aggressive polling or unnecessary data pushes.

## 2. The "Reviewstack-Greek" Goal Proposal
We intend to create a new Beeminder goal for Greek reviews to mirror the existing Arabic `reviewstack` goal.

### Goal Configuration
- **Slug:** `reviewstack-greek`
- **Title:** "Cards in Review stack (Clozemaster Greek)"
- **Source:** Automated scrape from Clozemaster via `mecris` backend.
- **Metric:** Number of cards ready for review (Target: 0).

## 3. Implementation Philosophy: "Thoughtful Motion"
We are explicitly choosing **not** to implement this today. We will follow a "Vertical Slice" observation period:

1.  **Observation (7-14 Days):** 
    - Monitor the reliability of the current manual syncs (Android → MCP → Scraper).
    - Observe if the "Review Pump" velocity calculations in the MCP server provide actionable coaching.
    - Ensure the Health Connect sync (Issue #76) remains stable before adding more data dependencies.
2.  **API Budgeting:** 
    - Design a "Smart Push" mechanism that only sends data to Beeminder when the value changes significantly or once per day (Midnight Sync).
    - Avoid "Ghost Worker" spam (already addressed in Android, but must be maintained in the Spin/Python backends).
3.  **Correction Before Compounding:**
    - If we notice that the current scraper/sync design has flaws (e.g., session timeouts, 403s from Clozemaster), we will fix the core architecture **before** creating the Greek goal.

## 4. Next Steps (Scheduled for ~March 22, 2026)
- Review the `SESSION_LOG` from the past week.
- If stability is >95%, proceed with creating the `reviewstack-greek` goal on Beeminder.
- Update `scripts/clozemaster_scraper.py` to enable the push for the new slug.

---
*This plan prioritizes correctness and stewardship over immediate velocity.*
