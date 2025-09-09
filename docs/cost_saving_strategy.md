# Cost‑Saving Strategy for Multi‑Terminal Claude Code

**Purpose** – Explain how the three‑proxy architecture (free Groq, paid Groq, paid Anthropic) turns the existing multi‑terminal workflow into a measurable money‑saving engine while allowing us to broaden the scope of the five Mecris projects.

---

## 1. Proxy Landscape (Three Instances)
| Proxy | Tier | Primary Role |
|-------|------|--------------|
| **proxy‑free‑groq** | Free (unauthenticated) | Optimistic first‑hit; most requests attempt here. |
| **proxy‑paid‑groq** | Paid Groq (low‑cost) | Fallback when the free tier shows signs of throttling. |
| **proxy‑paid‑anthropic** | Paid Claude (high‑cost) | Final fallback for critical or high‑value requests.

The routing script queries the **service mesh** for real‑time back‑pressure signals (e.g., `429 Too Many Requests`). When a signal is detected, the mesh forwards the request to the next proxy in the chain.

---

## 2. Intelligent Retry & Holding Queue
- The mesh **holds** failed free‑tier requests instead of immediately bubbling an error to the orchestrator.
- Held requests are **re‑enqueued** after a short back‑off, giving the free tier a chance to recover.
- Only after a configurable number of retries does the mesh promote the request to the paid‑Groq proxy, and finally to Claude if needed.

This approach maximizes the proportion of requests that succeed on the free tier, directly translating into cost avoidance.

---

## 3. Quantifying Savings
| Metric | Definition |
|--------|------------|
| **Free‑tier savings** | Count of successful requests served by `proxy‑free‑groq` (first attempt + retries). Multiply by the unit cost of a paid request to estimate dollars saved. |
| **Groq‑vs‑Claude savings** | Count of requests that completed on `proxy‑paid‑groq` instead of escalating to Claude. Multiply by the price differential (`Claude $X` – `Groq $Y`). |
| **Retry‑avoidance savings** | Requests that would have errored on the free tier but succeeded after the mesh‑managed retry. Treated as additional free‑tier savings. |

All metrics are exported to the **budgetary accounting worksheet** (`budget.xlsx` in the repo) via a tiny side‑car collector that logs:
```json
{ "timestamp": "2025-09-09T12:34Z", "proxy": "free-groq", "saved_usd": 0.00012 }
```
The worksheet aggregates daily totals, giving us a clear picture of **money saved vs. money spent**.

---

## 4. Long‑Term Planning Integration
1. **Budget‑aware routing** – The routing script periodically reads the `/usage` endpoint to check remaining Claude credits. When the credit balance falls below a threshold, the mesh raises the **escalation aggressiveness** (i.e., prefers paid‑Groq sooner). This protects the remaining credits for high‑impact tasks.
2. **Scope expansion** – Because the free tier handles the bulk of low‑value traffic, we can safely increase the number of concurrent terminals or add new projects without a linear increase in spend.
3. **Feedback loop** – After each orchestrator checkpoint, the orchestrator updates a **budget health badge** in the shared `README.md`, showing:
   - `Saved: $X`
   - `Spent: $Y`
   - `Net: $X‑$Y`
   This visible metric keeps the team aligned on the cost‑saving goal.

---

## 5. Summary
- Deploy **three** `claude-code-proxy` instances, ordered by cost.
- Use the **service mesh** to detect throttling, hold & retry, and gracefully promote requests.
- Export per‑request savings to a **budget worksheet**, enabling daily accounting of avoided spend.
- The system lets us **scale the multi‑terminal workflow** across all five Mecris projects while keeping the financial impact minimal.

By turning throttling into an opportunity for intelligent fallback, the strategy turns “free‑tier failures” into **explicit dollar‑saving events**, directly supporting the broader Mecris mission of delivering more value with limited resources.
