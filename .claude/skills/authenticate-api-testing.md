# Skill: Authenticate for API Testing with Mecris CLI

## Purpose
Get a valid Pocket ID access token for testing Mecris API endpoints (local Python MCP server, Akamai/Fermyon cloud backends).

## Prerequisites
- Mecris CLI installed (`bin/mecris` in PATH or run via `.venv/bin/python -m cli.main`)
- Pocket ID configured at `https://metnoom.urmanac.com`
- Client ID: `21f65a91-c4df-468d-a256-3b66a54c6d5f`

## Procedure

### 1. Run Login Flow
```bash
cd /Users/yebyen/w/mecris
.venv/bin/python -m cli.main login
```

This will:
- Check for valid cached tokens in `~/.mecris/credentials.json`
- Attempt silent refresh using stored `refresh_token`
- If expired/missing, open browser to Pocket ID for OIDC PKCE flow
- Save new tokens to `~/.mecris/credentials.json`

### 2. Extract Access Token
```bash
cat ~/.mecris/credentials.json | jq -r .access_token
```

Or in one line:
```bash
ACCESS_TOKEN=$(.venv/bin/python -c "
import json
with open('/Users/yebyen/.mecris/credentials.json') as f:
    print(json.load(f)['access_token'])
")
```

### 3. Test API Endpoint

**Local Python MCP Server (port 8080, auth_bypass enabled):**
```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8080/languages
curl -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8080/aggregate-status
curl -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8080/budget
curl -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8080/health
```

**Akamai Cloud (production, full JWT verification):**
```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/languages
curl -H "Authorization: Bearer $ACCESS_TOKEN" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/aggregate-status
```

**Fermyon Cloud (production):**
```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" https://mecris-sync-v2-glo0zpfm.fermyon.app/languages
```

## Token Format
The access token is a JWT with these claims:
- `sub`: User ID (e.g., `c0a81a4b-115a-4eb6-bc2c-40908c58bf64`)
- `iss`: `https://metnoom.urmanac.com`
- `aud`: `["21f65a91-c4df-468d-a256-3b66a54c6d5f"]`
- `exp`: Unix timestamp (1 hour from issuance)

## Troubleshooting

**"Authentication failed" on cloud endpoints:**
- Pocket ID SSL cert may be expired (Synology 404 page instead of OIDC endpoints)
- Check `curl https://metnoom.urmanac.com/.well-known/jwks.json` — should return JSON, not HTML
- If expired, renew Let's Encrypt cert on Synology or use local server

**"Silent refresh failed":**
- Delete `~/.mecris/credentials.json` and re-run login
- Check Pocket ID is reachable: `curl -I https://metnoom.urmanac.com/authorize`

**Local server returns 401:**
- Ensure `MECRIS_MODE=standalone` is set (enables auth bypass for `TestUser` prefix)
- Or use real token from Pocket ID (as shown above)

## Quick One-Liner for Testing
```bash
cd /Users/yebyen/w/mecris && .venv/bin/python -m cli.main login 2>/dev/null && TOKEN=$(.venv/bin/python -c "import json; print(json.load(open('/Users/yebyen/.mecris/credentials.json'))['access_token'])") && curl -s -H "Authorization: Bearer $TOKEN" https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/languages | jq '.languages[] | {name, current, tomorrow, daily_completions, absolute_target, goal_met, has_goal, safebuf, derail_risk}'
```

## Related Skills
- `/mecris-orient` — Situation report including auth status
- `/mecris-plan` — Write spec before making API changes