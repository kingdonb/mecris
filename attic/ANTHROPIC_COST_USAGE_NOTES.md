# Anthropic Cost & Usage API Integration Notes

## API Access Requirements
- Requires **Organization-level access**
- Needs a specific **Admin API key** from Anthropic Console
- Different from regular `ANTHROPIC_API_KEY`

## Discovered Endpoints
1. `/v1/usage-cost/get-messages-usage-report`
2. `/v1/usage-cost/get-cost-report`

## Authentication
- Uses `x-api-key` header
- Requires `anthropic-version: 2023-06-01`

## Current Limitations
- Cannot use individual account API key
- Requires explicit organization admin access

## Local Tracking Status
- Current remaining budget: $19.54
- Days remaining: 19

## Next Steps
- Obtain organization-level admin API key
- Confirm full API integration capabilities
- Implement robust error handling
- Set up continuous usage monitoring

## Observations
- API returns 404 when incorrectly configured
- MCP server provides fallback local tracking
- Test script demonstrates endpoint discovery