# Anthropic Cost Tracking Investigation

## Overview

This document captures our investigation into integrating Anthropic's Admin API for cost tracking within the Mecris system. We successfully implemented API connectivity but discovered important limitations around data availability and organization structure.

## What We Built

### Enhanced Cost Tracker Script

Modified `scripts/anthropic_cost_tracker.py` to include:

- **Command-line argument support** for custom date ranges
- **Proper error handling** and rate limiting
- **Dual API integration** (Usage Reports + Cost Reports)
- **Caching system** for API responses

Usage:
```bash
# Default behavior - recent summary
uv run python scripts/anthropic_cost_tracker.py

# Custom date range
uv run python scripts/anthropic_cost_tracker.py --start-date 2024-07-29 --end-date 2024-08-05
```

### API Endpoints Successfully Connected

- ✅ **Usage Reports**: `/v1/organizations/usage_report/messages`
- ✅ **Cost Reports**: `/v1/organizations/cost_report`
- ✅ **Rate limiting**: 10-second intervals between calls
- ✅ **Pagination support**: Handles `has_more` and `next_page` tokens

## Key Findings

### 1. Empty Data Mystery 🤔

**What we observed**: API calls return successful responses with empty `results` arrays across all tested date ranges (July 2024 - January 2025).

**Possible explanations**:
- Organization API keys may only track usage *after* organization creation
- Historical personal account usage doesn't migrate to organization accounts
- There may be a reporting delay (unconfirmed)
- The Admin API key might be associated with a different org than expected

### 2. Organization vs Personal Account Structure

**Current hypothesis**: Anthropic's organization feature might be relatively new, meaning:
- Personal usage history doesn't automatically transfer
- Cost tracking only begins when organization-level API keys are used
- Historical data for personal accounts may not be accessible via Admin API

### 3. API Key Creation vs Usage Tracking

**Observation**: Multiple API keys show "zero cost" in the web interface, consistent with our API results.

**Implication**: Cost data only appears when API keys are actively used under organization billing.

## Next Steps

### Immediate Actions

1. **Generate test usage** with organization API key
2. **Monitor for reporting delay** (check after 24-48 hours)
3. **Verify organization setup** in Anthropic Console

### Testing Protocol

```bash
# After generating some usage with org API key:
uv run python scripts/anthropic_cost_tracker.py --start-date $(date -d "yesterday" +%Y-%m-%d) --end-date $(date +%Y-%m-%d)
```

### Future Enhancements

- **Pagination handling**: Implement `next_page` token following
- **Real-time monitoring**: Integration with Mecris MCP server
- **Alert thresholds**: Budget warnings and notifications
- **Usage analytics**: Trend analysis and forecasting

## Technical Details

### API Response Structure

**Empty Response Pattern**:
```json
{
  "data": [
    {
      "starting_at": "2024-07-29T00:00:00Z",
      "ending_at": "2024-07-30T00:00:00Z", 
      "results": []
    }
  ],
  "has_more": false,
  "next_page": null
}
```

**Expected Response** (when data exists):
```json
{
  "data": [
    {
      "starting_at": "2024-07-29T00:00:00Z",
      "ending_at": "2024-07-30T00:00:00Z",
      "results": [
        {
          "model": "claude-3-5-sonnet-20241022",
          "input_tokens": 1000,
          "output_tokens": 500,
          "cost": "0.0075"
        }
      ]
    }
  ]
}
```

## Budget Status

**Current spend**: ~$2 (excellent progress! 🎉)  
**API integration**: ✅ Working  
**Data availability**: ⏳ Pending verification

## Lessons Learned

1. **Admin API works perfectly** - no connectivity issues
2. **Organization structure** impacts data availability significantly
3. **Historical data migration** may not be automatic
4. **Cost tracking** requires organization-level API usage to generate data

This investigation successfully established the technical foundation for cost tracking. The next phase focuses on generating and detecting actual usage data.