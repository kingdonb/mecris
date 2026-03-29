# 🏛️ Budget Governor Implementation Guide (Lab of Excellence)

Welcome to the Lab, `mecris-bot`. Your task is to build the "Fiscal Intelligence" layer of Mecris: **The Budget Governor**.

This is not a simple script. It requires architectural thinking. Here is some guidance from your Senior Architect (Gemini) to help you hit the ground running.

## 1. Architectural Placement
Do NOT stuff this into `usage_tracker.py`. It is already 500+ lines.
Instead, create a new module: `services/budget_governor.py`.

## 2. The Helix API Secret
You are already configured to hit the Helix API! Look at your own GitHub Actions workflow (`.github/workflows/mecris-bot.yml`).
You have access to:
*   `ANTHROPIC_BASE_URL` (Pointing to Helix)
*   `ANTHROPIC_API_KEY` (Your Helix token)

**API Reference (Extracted from Documentation):**
*   **Base URL (SaaS):** `https://app.tryhelix.ai/api/v1`
*   **Inference URL:** `https://app.tryhelix.ai/v1` (OpenAI/Anthropic compatible)
*   **Headers:** Standard `Authorization: Bearer YOUR_API_KEY`
*   **Key Discovery Endpoints:**
    - `GET /api/v1/apps` - List agents/apps (may contain quota context)
    - `GET /api/v1/sessions` - List past sessions for usage tracking
    - **Interactive Reference:** `https://docs.helixml.tech/helix/api-reference/`

**Your First Mission (Discovery):** Before building the logic, write a quick test script to hit the Helix API and see if you can retrieve the credit balance (e.g., `$97.83`). 
Try hitting `/api/v1/apps` or look for a billing/usage endpoint in the interactive docs. If you can fetch the live balance, the "Helix Inversion" logic becomes incredibly powerful. If you can't, you will need to rely on local usage counting.

## 3. Core Concepts to Implement

### A. The 5%/5% Rate Envelope
*   Calculate the "daylight window" (13 hours = 780 minutes).
*   5% of that window is ~39 minutes.
*   Your Governor must ensure that in any rolling 39-minute window, no more than 5% of a bucket's total period quota is spent.
*   *Hint:* You will need a way to track "spend events" with timestamps to calculate the rolling window.

### B. The Routing Logic (The Inversion)
*   **Anthropic / Groq:** Traditional. Stop spending when near the limit.
*   **Helix / Gemini:** Inverted. These are *use-it-or-lose-it* credits. 
*   If Helix credits are high, the Governor should return a recommendation to *route heavy tasks to Helix*.

## 4. Suggested Skeleton (`services/budget_governor.py`)

```python
from enum import Enum
from typing import Dict, Any, Optional
import os

class BucketType(Enum):
    GUARD = "guard"  # e.g., Anthropic, Groq (ration these)
    SPEND = "spend"  # e.g., Helix, Gemini (use these up)

class BudgetGovernor:
    def __init__(self):
        # Initialize buckets
        self.buckets = {
            "helix": {"type": BucketType.SPEND, "limit": 100.00},
            "anthropic_api": {"type": BucketType.GUARD, "limit": 20.89},
            # Add Groq, Gemini CLI, etc.
        }

    def check_envelope(self, bucket_name: str, cost_estimate: float) -> str:
        """Returns 'allow', 'defer', or 'deny' based on the 5%/5% rule."""
        pass

    def recommend_bucket(self, task_type: str = "general") -> str:
        """Returns the best available bucket. Prioritizes SPEND buckets if available."""
        pass
        
    def get_helix_balance(self) -> Optional[float]:
        """Attempt to fetch live balance from Helix API using os.getenv('ANTHROPIC_BASE_URL')."""
        pass
```

## 5. Exposing it via MCP
Once `BudgetGovernor` is built, go to `mcp_server.py` and expose it as a tool:
```python
@mcp.tool()
async def get_budget_governor_status() -> Dict[str, Any]:
    """Returns per-bucket consumption, envelope status, and a routing recommendation."""
```

Take your time. Iterate in your fork. Prove the logic works with unit tests before you open a PR. Good luck! 🚀
