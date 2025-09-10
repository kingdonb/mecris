# Multi-Provider Billing System - Decision Document

## Current State Assessment

### ✅ What's Working
- **Virtual Budget Manager**: Core financial control system functional
- **Anthropic Integration**: Real-time API working perfectly ($0.10+ detected)
- **Database Schema**: Multi-provider tracking ready
- **MCP Endpoints**: 15+ new endpoints for budget management
- **Budget Controls**: Real-time spending limits and emergency overrides

### ❌ What's Broken/Incomplete
- **Groq Scraper**: OAuth authentication not implemented (password-based login won't work)
- **Daily Reconciliation**: Requires automation decision - cron job vs manual triggers
- **Production Deployment**: No deployment strategy defined
- **Error Handling**: Groq scraping failures not gracefully handled

### 🤔 Architecture Decisions Needed

## Decision Point 1: Groq Data Collection Strategy

**Problem**: Groq uses OAuth, not username/password. Current scraper is non-functional.

**Options**:

### A) Cookie-Based Scraping (Quick Fix)
```python
# Extract cookies from authenticated browser session
cookies = [
    {"name": "session_token", "value": "abc123...", "domain": ".groq.com"}
]
# Use cookies in Playwright context
```
**Pros**: Can implement immediately, works with existing infrastructure
**Cons**: Cookies expire, requires manual refresh, brittle

### B) OAuth Integration (Proper Solution)
```python
# Implement proper OAuth flow
oauth_client = GroqOAuthClient(client_id, client_secret, redirect_uri)
token = oauth_client.get_access_token()
```
**Pros**: Sustainable, follows API best practices
**Cons**: More complex, requires Groq developer account setup

### C) Manual Entry (Fallback)
```python
# User manually enters monthly spend
manager.record_groq_usage_manual(monthly_total=1.06)
```
**Pros**: Simple, always works
**Cons**: Not automated, prone to user error

**RECOMMENDATION**: Start with C (manual entry) for immediate functionality, implement B (OAuth) when Groq releases billing API.

## Decision Point 2: Daily Reconciliation Automation

**Problem**: System needs to sync estimates with actual billing data. Currently requires manual trigger.

**Options**:

### A) Cron Job Automation
```bash
# /etc/crontab
0 6 * * * cd /path/to/mecris && uv run python billing_reconciliation.py
```
**Pros**: Fully automated, consistent daily accuracy
**Cons**: Requires system administration, another moving part

### B) MCP Endpoint Triggers
```python
# Manual trigger via API call
POST /billing/reconcile/daily
# Or integrated into daily narrator context
```
**Pros**: On-demand control, integrates with existing workflows
**Cons**: Requires human intervention, may be forgotten

### C) Startup Reconciliation
```python
# Run reconciliation when MCP server starts
if last_reconciliation > 24_hours_ago:
    billing_reconciler.daily_reconciliation()
```
**Pros**: Automatic without cron, happens during natural server restarts
**Cons**: Inconsistent timing, may not run for days

**RECOMMENDATION**: Start with B (manual MCP triggers), add A (cron) if we prove daily usage patterns.

## Decision Point 3: Production Deployment Strategy

**Current State**: Development-ready system with test database

**Options**:

### A) Dual System Transition
```python
# Run both old and new systems in parallel
old_result = usage_tracker.record_session(...)
new_result = virtual_budget_manager.record_usage(...)
# Compare results, gradually migrate endpoints
```
**Pros**: Safe migration, can compare accuracy
**Cons**: Duplicate data, temporary complexity

### B) Clean Cut Migration
```python
# Replace usage_tracker entirely
# Migrate existing data to new schema
# Update all MCP endpoints at once
```
**Pros**: Clean architecture, no duplication
**Cons**: Risky, potential data loss

### C) Staged Rollout
```python
# Week 1: New system for new usage only
# Week 2: Migrate budget endpoints
# Week 3: Full cutover
```
**Pros**: Controlled risk, gradual validation
**Cons**: Extended migration period

**RECOMMENDATION**: A (dual system) for immediate deployment, validate for 1 week, then clean cutover.

## Decision Point 4: Cost vs Capability Trade-offs

**Budget Reality**: ~22 hours of Claude credits remaining

**High-Impact, Low-Cost Actions**:
1. **Fix Groq manual entry**: 30 minutes - enables multi-provider tracking
2. **Deploy dual system**: 1 hour - immediate production value
3. **Add budget alerts to narrator**: 1 hour - prevents overspend

**Medium-Impact, Medium-Cost Actions**:
4. **Groq OAuth integration**: 3-4 hours - sustainable data collection
5. **Web dashboard**: 4-5 hours - visual budget monitoring
6. **Advanced cost optimization**: 2-3 hours - automatic provider selection

**High-Impact, High-Cost Actions**:
7. **Full reconciliation ML**: 6+ hours - predictive budgeting
8. **Enterprise features**: 8+ hours - multi-user, accounting integration

**RECOMMENDATION**: Focus on items 1-3 (6 hours total) for maximum immediate value.

## Immediate Action Plan (Next 6 Hours)

### Hour 1: Fix Groq Integration
```python
def record_groq_usage_manual(monthly_spend: float, days_in_month: int = 30):
    daily_estimate = monthly_spend / days_in_month
    # Record estimated daily usage
```

### Hour 2: Deploy Dual System
- Keep existing usage_tracker running
- Add virtual_budget_manager alongside
- Update key MCP endpoints to use both

### Hour 3: Add Budget Alerts
```python
# In narrator context
if virtual_budget_status["budget_health"] == "CRITICAL":
    urgent_items.append("🚨 BUDGET CRITICAL: Emergency measures needed")
```

### Hours 4-6: Validation & Documentation
- Test dual system with real usage
- Document migration procedures
- Create operator runbooks

## Questions for Opus

1. **Groq Strategy**: Should we prioritize OAuth integration or accept manual entry for now?
2. **Automation Level**: Do you want cron jobs, or prefer manual control of reconciliation?
3. **Migration Risk**: Dual system vs clean cutover - what's your risk tolerance?
4. **Feature Priority**: Budget alerts, web dashboard, or cost optimization first?
5. **Technical Debt**: Address Groq scraper properly or ship workaround?

## Success Metrics

**Week 1 Goals**:
- Multi-provider usage tracking working
- Budget controls preventing overspend  
- Daily reconciliation (manual trigger) improving accuracy
- Documentation complete for handoff

**Week 2+ Goals** (for future sprints):
- Groq OAuth integration working
- Automated reconciliation running daily
- Cost optimization routing to cheapest provider
- Web dashboard for visual budget monitoring

## Risk Assessment

**High Risk**:
- Groq scraper completely non-functional without OAuth/cookies
- Cron job dependency introduces system administration complexity
- Dual system deployment could confuse existing workflows

**Medium Risk**:
- Budget constraints too restrictive for real usage patterns
- Reconciliation accuracy depends on provider API reliability
- Token cost calculations may drift from actual billing

**Low Risk**:
- Virtual budget architecture is solid and tested
- Anthropic integration working perfectly
- Database schema handles all planned use cases

This system transforms Mecris from simple cost tracking to enterprise-grade multi-provider financial management - but needs these decisions resolved for production deployment.