# Claude API Credit Tracking Limitations

## Current Status

**❌ Problem**: Anthropic does not provide a public API endpoint for retrieving credit balance information programmatically.

**✅ Solution**: Mecris uses local budget tracking with manual updates to monitor Claude API usage and spending.

## Technical Details

### What's NOT Available
- No public API endpoint for credit balance retrieval
- No programmatic access to billing information
- No real-time credit consumption tracking from Anthropic

### What Mecris Implements Instead

#### 1. Local Usage Tracking (`usage_tracker.py`)
- **SQLite database** stores usage sessions with token counts and cost estimates
- **Accurate pricing** based on current Claude API rates
- **Budget management** with manual updates and alerts
- **Daily burn rate** calculation and projection

#### 2. Manual Budget Updates
- **REST endpoint**: `POST /usage/update_budget` for balance updates
- **Integrated scraper scaffolding** for future automation
- **Cache system** to minimize manual updates

#### 3. Cost Estimation
- **Token-based calculation** using official Anthropic pricing
- **Model-specific rates** (Claude-3.5-Sonnet, Claude-3.5-Haiku)
- **Session tracking** by type (interactive, emergency, etc.)

## Current Pricing (as of August 2025)

### Claude-3.5-Sonnet
- **Input tokens**: $3.00 per million tokens
- **Output tokens**: $15.00 per million tokens

### Claude-3.5-Haiku  
- **Input tokens**: $0.25 per million tokens
- **Output tokens**: $1.25 per million tokens

## Usage Workflow

### 1. Initial Setup
```bash
# Budget is initialized in usage_tracker.py
# Default: $20.26 total, $18.21 remaining, expires 2025-08-05
```

### 2. Manual Balance Updates
```bash
# Update remaining balance when you check Anthropic Console
curl -X POST http://localhost:8000/usage/update_budget \
  -H "Content-Type: application/json" \
  -d '{"remaining_budget": 15.50}'
```

### 3. Automatic Usage Recording
- Mecris automatically records token usage for each session
- Cost estimation is applied immediately
- Budget tracking updates in real-time

### 4. Budget Monitoring
```bash
# Check current budget status
curl http://localhost:8000/usage
```

## Alert System

### Budget Thresholds
- **CRITICAL**: < $5 remaining OR < 1 day left
- **WARNING**: < $10 remaining OR < 2 days left
- **CAUTION**: High daily burn rate

### Notification Methods
- **Twilio SMS** alerts for critical budget situations
- **API responses** include budget health indicators
- **Logs** track all budget changes and alerts

## Future Implementation Options

### 1. Web Scraping (Scaffolded)
- **File**: `claude_api_budget_scraper.py` 
- **Approach**: Automate Anthropic Console login and balance extraction
- **Challenges**: ToS compliance, authentication, page structure changes
- **Status**: Scaffolding implemented, requires Playwright/Selenium

### 2. Browser Extension
- Chrome/Firefox extension to capture balance automatically
- Runs in background, updates Mecris via API
- Less intrusive than full web scraping

### 3. Email Parsing
- Parse Anthropic billing notification emails
- Extract balance information automatically
- Requires email access integration

### 4. Manual Process (Current)
- Check Anthropic Console periodically
- Update Mecris budget via API call
- Most reliable until official API is available

## API Endpoints

### Budget Management
- `GET /usage` - Current budget status
- `POST /usage/update_budget` - Manual balance update
- `POST /usage/record` - Record usage session
- `GET /usage/summary` - Detailed usage report

### Monitoring
- `GET /usage/recent` - Recent usage sessions
- `POST /usage/alert` - Check and send budget alerts

## Recommendations

### For Development
1. **Use the manual update system** - most reliable
2. **Check Anthropic Console weekly** - update Mecris budget
3. **Monitor daily burn rate** - adjust usage patterns
4. **Set conservative thresholds** - avoid surprise overages

### For Production
1. **Implement browser extension** - if scaling usage
2. **Schedule regular balance checks** - automation via cron/scheduled tasks
3. **Consider multiple API keys** - distribute usage across accounts
4. **Monitor Anthropic announcements** - watch for official balance API

## Integration Examples

### Update Budget from Console Check
```python
from claude_api_budget_scraper import update_balance_manually

# After checking Anthropic Console, update Mecris
balance = update_balance_manually(
    remaining=15.50,
    total=25.00,
    period_end="2025-08-05"
)
print(f"Updated: ${balance.remaining_credits:.2f} remaining")
```

### Check Budget Before Large Tasks
```python
import requests

response = requests.get("http://localhost:8000/usage")
budget = response.json()

if budget["days_remaining"] < 1:
    print("⚠️ Critical: Less than 1 day of budget remaining")
    # Scale back or pause non-essential tasks
```

## Conclusion

While Anthropic doesn't provide programmatic balance access, Mecris's local tracking system provides:

- ✅ **Accurate cost estimates** based on token usage
- ✅ **Real-time budget monitoring** with alerts
- ✅ **Historical usage analysis** for optimization
- ✅ **Future-ready architecture** for when APIs become available

The current system is production-ready and provides better insights than many commercial API management tools.