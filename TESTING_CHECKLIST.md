# 🧪 MCP Testing Checklist

## Pre-Testing Setup
- [ ] Start mcp-obsidian server on localhost:3001
- [ ] Set environment variables: `BEEMINDER_USERNAME`, `BEEMINDER_AUTH_TOKEN`
- [ ] Set `OBSIDIAN_VAULT_PATH` to your vault location
- [ ] Configure Twilio: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TWILIO_TO_NUMBER`

## Health Checks
```bash
curl http://localhost:8000/health
# Should show all services as "ok" or "not_configured"
```

## Obsidian Integration Tests
```bash
# Test goal extraction
curl http://localhost:8000/goals

# Test todo extraction  
curl http://localhost:8000/todos

# Test daily note (replace date)
curl http://localhost:8000/daily/2025-07-30
```

## Beeminder Integration Tests
```bash
# Test goal status
curl http://localhost:8000/beeminder/status

# Test emergencies
curl http://localhost:8000/beeminder/emergency
```

## Narrator Context Test
```bash
curl http://localhost:8000/narrator/context
# Should aggregate all sources with recommendations
```

## Session Logging Test
```bash
curl -X POST http://localhost:8000/log-session \
  -H "Content-Type: application/json" \
  -d '{"duration":"5 min","actions_taken":["tested API"],"outcomes":"verified functionality"}'
```

## Critical Test: No Write Access to Beeminder
- ✅ Confirm `add_datapoint()` method exists but NO endpoint exposes it
- ✅ Only GET requests in MCP server endpoints