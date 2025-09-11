# MCP Reconciliation Workflow Design

## Problem Statement

Current system has a "manual plug" where the $19.54 remaining budget is accurate (manually tracked), but we need to reconcile this with automatic session tracking to maintain proper bookkeeping.

**Current State**:
- ✅ $19.54 remaining budget = CORRECT (manual tracking)  
- ❌ $5.31 "ghost usage" = Real Claude usage outside org workspace (not auto-tracked)
- ❌ Manual updates via `scripts/update_budget.sh`

## Solution: MCP Reconciliation Workflow

### 1. Enhanced Budget Reconciliation Table

Add reconciliation tracking to existing database:

```sql
CREATE TABLE budget_reconciliation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reconciliation_date DATE,
    budget_before REAL,
    manual_adjustment REAL,
    budget_after REAL,  
    adjustment_reason TEXT,
    api_usage_tracked REAL,
    manual_plug_amount REAL,
    reconciled_by TEXT DEFAULT 'mcp-workflow',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. New MCP Endpoints

#### A. `mcp__mecris__record_budget_reconciliation`
```python
def record_budget_reconciliation(
    current_budget: float,
    manual_adjustment: float, 
    adjustment_reason: str = "anthropic-console-sync"
):
    """
    Record a budget reconciliation event with proper plug tracking
    
    Args:
        current_budget: True remaining budget from Anthropic Console
        manual_adjustment: Difference between tracked usage and reality  
        adjustment_reason: Why this adjustment was needed
    
    Returns:
        reconciliation_id, updated_budget_status
    """
```

#### B. `mcp__mecris__get_reconciliation_status` 
```python
def get_reconciliation_status(days: int = 7):
    """
    Get recent reconciliation history and budget integrity status
    
    Returns:
        - Recent reconciliations
        - Total manual adjustments  
        - Budget tracking health
        - Recommended actions
    """
```

### 3. Workflow Implementation

#### Step 1: Automated Budget Sync
Replace `scripts/update_budget.sh` with:

```python
# New: mcp_reconcile_budget.py
import sys
from mcp_client import MCPClient

def reconcile_budget(remaining_budget: float, total_budget: float = None):
    client = MCPClient()
    
    # Get current tracked budget
    current_status = client.get_budget_status()
    
    # Calculate manual adjustment needed
    tracked_remaining = current_status['remaining_budget']
    manual_adjustment = remaining_budget - tracked_remaining
    
    # Record reconciliation with proper tracking
    result = client.record_budget_reconciliation(
        current_budget=remaining_budget,
        manual_adjustment=manual_adjustment,
        adjustment_reason="anthropic-console-sync"
    )
    
    # Update budget through MCP (maintains audit trail)
    client.update_budget(
        remaining_budget=remaining_budget,
        total_budget=total_budget
    )
    
    return result
```

#### Step 2: Daily Reconciliation Integration
Enhance existing `billing_reconciliation.py`:

```python
def reconcile_claude_budget(self) -> ReconciliationResult:
    """
    Reconcile Claude budget with Anthropic Console reality
    """
    try:
        # Get current MCP budget status
        budget_status = self.get_mcp_budget_status()
        
        # Get actual budget from Anthropic Console (future: API integration)
        actual_budget = self.get_anthropic_console_budget()
        
        if actual_budget != budget_status['remaining_budget']:
            # Record the reconciliation
            adjustment = actual_budget - budget_status['remaining_budget']
            self.record_mcp_reconciliation(
                current_budget=actual_budget,
                manual_adjustment=adjustment,
                adjustment_reason="daily-reconciliation-check"
            )
            
            # Update budget through MCP
            self.update_mcp_budget(actual_budget)
            
        return ReconciliationResult(
            provider="claude-budget",
            success=True,
            manual_adjustment=adjustment
        )
        
    except Exception as e:
        return ReconciliationResult(
            provider="claude-budget", 
            success=False,
            error=str(e)
        )
```

### 4. MCP Integration Points

#### Update `mcp_server.py` to include:

```python
# New reconciliation endpoints
@app.post("/budget/reconcile")  
async def reconcile_budget_endpoint(...):
    """Main budget reconciliation endpoint"""

@app.get("/budget/reconciliation/history")
async def get_reconciliation_history_endpoint(...):
    """Get reconciliation audit trail"""

@app.post("/budget/reconciliation/manual")
async def record_manual_reconciliation_endpoint(...): 
    """Record manual budget adjustments with reasons"""
```

### 5. Audit Trail & Compliance

#### Every budget change gets recorded:
```json
{
    "reconciliation_date": "2025-09-10",
    "budget_before": 19.54,
    "manual_adjustment": -5.31,
    "budget_after": 14.23,
    "adjustment_reason": "anthropic-console-sync",
    "api_usage_tracked": 0.11,
    "manual_plug_amount": 5.31,
    "reconciled_by": "mcp-workflow"
}
```

## Benefits

### ✅ Maintains Accuracy
- $19.54 remains correct (manual tracking)
- But now we track WHY it's different from auto-tracked usage

### ✅ Proper Bookkeeping  
- Manual adjustments are recorded with reasons
- Full audit trail of budget changes
- Can tie out: Auto-tracked + Manual adjustments = Total spend

### ✅ MCP Integration
- All budget changes flow through MCP server
- Consistent API for budget management
- No more direct database manipulation

### ✅ Future-Proof
- When Anthropic billing API becomes available, easy to switch
- Reconciliation framework works for any provider
- Historical adjustment data preserved

## Implementation Plan

1. **Add reconciliation table and MCP endpoints** 
2. **Create `mcp_reconcile_budget.py` script**
3. **Enhance daily reconciliation workflow**  
4. **Test with current $19.54 budget state**
5. **Replace manual script workflow**

## Migration Strategy

### Phase 1: Parallel System
- Keep `update_budget.sh` working
- Add reconciliation tracking alongside
- Validate numbers match

### Phase 2: MCP Migration  
- Replace script with MCP reconciliation
- Maintain audit trail
- Monitor for any discrepancies

### Phase 3: Full Automation
- Daily reconciliation includes budget sync
- Manual adjustments become rare exceptions
- Complete financial control through MCP

This design preserves the accurate $19.54 budget while adding proper reconciliation tracking and MCP integration.