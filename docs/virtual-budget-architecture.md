# Virtual Budget Management Architecture

## The Fundamental Problem

Traditional LLM billing systems use two incompatible models:

1. **Prepaid Credits** (Claude): Buy credits upfront, spend them down
2. **Postpaid Usage** (Groq): Pay for usage after the fact

Neither provider offers a "credits remaining" API because:
- **Anthropic**: Only provides usage/cost data, not remaining balance
- **Groq**: Bills retrospectively, no concept of prepaid credits

## Our Solution: Virtual Budget System

We create an **internal budget management layer** that sits above all providers and manages spending allocation, regardless of their billing models.

### Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIRTUAL BUDGET LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│  • Budget Allocation ($X/day, $Y/month)                        │
│  • Real-time Cost Estimation                                   │
│  • Spending Pace Management                                    │
│  • Multi-provider Aggregation                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
        ┌───────▼───────┐ ┌─────▼─────┐ ┌─────▼─────┐
        │   ANTHROPIC   │ │    GROQ   │ │  FUTURE   │
        │   Real-time   │ │ Playwright│ │ PROVIDERS │
        │  Usage API    │ │  Scraping │ │           │
        └───────────────┘ └───────────┘ └───────────┘
```

### Key Components

#### 1. Budget Allocation Engine
- **Daily Budget**: Set realistic daily spending limits (e.g., $2/day)
- **Monthly Budget**: Set monthly caps with rollover logic
- **Provider Split**: Allocate budget across providers (e.g., 70% Claude, 30% Groq)
- **Emergency Reserves**: Hold back 20% for critical tasks

#### 2. Real-time Cost Estimation
- **Token-based Pricing**: Calculate costs immediately using token counts
- **Provider-specific Models**: Different pricing for Claude vs Groq models
- **Context Caching**: Account for Anthropic's sophisticated caching pricing
- **Confidence Intervals**: Track estimation accuracy vs actual costs

#### 3. Spending Pace Management
- **Hourly Burn Rate**: Spread daily budget across 24 hours
- **Peak Hour Allocation**: Allow higher spending during work hours (9am-6pm)
- **Off-hours Conservation**: Reduce spending at night/weekends
- **Emergency Bypass**: Override limits for critical tasks

#### 4. Reconciliation System
- **Daily Reconciliation**: Compare estimates vs actual billing
- **Provider Sync**: Pull real data from Anthropic API + Groq scraping
- **Drift Correction**: Adjust future estimates based on historical accuracy
- **Budget Rollover**: Handle unused daily budget allocation

## Implementation Strategy

### Phase 1: Foundation (Current Sprint)
```python
class VirtualBudgetManager:
    def __init__(self):
        self.daily_budget = 2.00        # $2/day target
        self.monthly_budget = 60.00     # $60/month cap
        self.emergency_reserve = 0.20   # 20% held back
        
    def allocate_spending(self, request_cost: float) -> bool:
        """Real-time spending decision"""
        if self.can_afford(request_cost):
            self.deduct_virtual_credit(request_cost)
            return True
        return False
```

### Phase 2: Multi-provider Integration
- **Anthropic Tracker**: Real-time usage via organization workspace API
- **Groq Scraper**: Cached Playwright script (15-minute intervals)
- **Local Estimates**: Immediate cost calculation for all requests
- **Reconciliation Jobs**: Daily sync to correct estimates

### Phase 3: Intelligence Layer
- **Usage Prediction**: ML-based spending forecasts
- **Dynamic Budgeting**: Adjust limits based on historical patterns
- **Provider Optimization**: Route requests to cheapest available provider
- **Cost Analytics**: Detailed spending insights and recommendations

## Benefits of This Architecture

### 1. Provider Agnostic
- Works regardless of billing model (prepaid vs postpaid)
- Easy to add new providers (future: OpenAI, Cohere, etc.)
- Consistent interface regardless of underlying APIs

### 2. Real-time Control
- Immediate spending decisions without waiting for billing data
- Prevents runaway costs from misconfigured automations
- Granular control over spending patterns

### 3. Accurate Reconciliation
- Daily correction of estimates using actual billing data
- Builds historical accuracy model for better predictions
- Handles edge cases like cached responses, bulk discounts

### 4. Flexible Budgeting
- Supports various budget models (daily, weekly, monthly)
- Emergency override capabilities for critical tasks
- Spending pattern optimization (work hours vs off-hours)

## Technical Implementation

### Database Schema
```sql
-- Virtual budget tracking
CREATE TABLE budget_allocations (
    id INTEGER PRIMARY KEY,
    period_type TEXT,           -- 'daily', 'monthly'
    budget_amount REAL,
    remaining_amount REAL,
    period_start DATE,
    period_end DATE
);

-- Multi-provider usage tracking
CREATE TABLE provider_usage (
    id INTEGER PRIMARY KEY,
    provider TEXT,              -- 'anthropic', 'groq'
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost REAL,
    actual_cost REAL,           -- null until reconciled
    timestamp DATETIME,
    reconciled BOOLEAN DEFAULT FALSE
);

-- Reconciliation tracking
CREATE TABLE reconciliation_jobs (
    id INTEGER PRIMARY KEY,
    provider TEXT,
    job_date DATE,
    estimated_total REAL,
    actual_total REAL,
    drift_percentage REAL,
    reconciled_at DATETIME
);
```

### Caching Strategy
- **Anthropic**: Real-time API (hourly buckets), 1-hour cache
- **Groq**: Playwright scraping, 15-minute cache, aggressive caching due to ToS
- **Local Estimates**: Immediate calculation, no caching needed

### Error Handling
- **API Failures**: Fall back to cached data with staleness warnings
- **Scraping Failures**: Use last known Groq data with degraded accuracy
- **Budget Exhaustion**: Emergency mode with manual override capability

## Migration from Current System

### Current State
- Local SQLite database with "credits remaining" concept
- Claude-only tracking with manual budget updates
- No real-time API integration

### Migration Steps
1. **Extend database schema** to support multiple providers
2. **Add virtual budget layer** while keeping existing local tracking
3. **Implement Groq integration** alongside existing Claude tracking
4. **Build reconciliation system** to sync estimates with reality
5. **Phase out manual budget updates** in favor of automatic reconciliation

This architecture transforms our billing system from a simple "credit tracker" into a sophisticated **financial control system** that can handle any provider, any billing model, and any usage pattern while maintaining strict cost control and accurate reporting.