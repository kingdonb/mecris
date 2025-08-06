# 🔧 Mecris Troubleshooting Guide

> **"When things break, fix them systematically. When they break again, document why."**

This guide addresses the most common Mecris failures and their solutions. Start here when tests fail or services misbehave.

---

## 🚨 Emergency Quick Fixes

### System Won't Start
```bash
# 1. Check if port is already in use
lsof -ti:8000 | xargs kill -9
# 2. Restart with clean slate  
source venv/bin/activate
python start_server.py
```

### All Tests Failing
```bash
# Check if MCP server is running
curl -s http://localhost:8000/health || echo "❌ Server down - start first"
# Restart and test
make restart && python -m pytest test_mecris_integration.py -v
```

---

## 🔍 Systematic Debugging Process

### 1. Health Check Triage
```bash
# Full system health assessment
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8000/narrator/context | head -20
curl -s http://localhost:8000/beeminder/status | jq
```

### 2. Service-by-Service Validation
```bash
# Test each component individually
curl -s http://localhost:8000/usage        # Budget tracking
curl -s http://localhost:8000/beeminder/status  # API connectivity
curl -s http://localhost:8000/obsidian/health   # Vault access
```

---

## 📊 Test Failure Resolution

### Failed: Obsidian Health Check (Status: unreachable)
**Expected**: Obsidian integration is work-in-progress per CLAUDE.md

**Quick Fix**: Skip for now
```bash
# Skip Obsidian tests until integration complete
pytest -k "not obsidian" test_mecris_integration.py
```

**Long-term Solution**: Complete Obsidian vault parsing (see TODO.md #3)

---

### Failed: Claude Monitor Health Check (Status: not_configured)
**Root Cause**: Missing Claude API credentials or claude_monitor not initialized

**Diagnosis**:
```bash
# Check if usage tracking database exists
ls -la claude_usage.json || echo "❌ No usage database"
# Verify environment setup
env | grep -i claude
```

**Fix**:
```bash
# Initialize usage tracking if missing
python -c "
import json
with open('claude_usage.json', 'w') as f:
    json.dump({'sessions': []}, f)
"
# Or check claude_monitor.py configuration
```

---

### Failed: API Budget Status (HTTP 404)
**Root Cause**: Route not found or server routing issue

**Diagnosis**:
```bash
# Check server logs for routing errors
curl -s http://localhost:8000/usage -v
# Verify FastAPI route registration
grep -r "usage" mcp_server.py
```

**Fix**: Ensure `/usage` endpoint is properly registered in `mcp_server.py`:
```python
@app.get("/usage")
async def get_usage():
    # Endpoint implementation
```

---

### Failed: Twilio Service (Status: configured)
**Root Cause**: Credentials configured but service health check failing

**Diagnosis**:
```bash
# Check Twilio configuration
env | grep TWILIO
# Test Twilio client directly
python -c "
from twilio_sender import TwilioSender
sender = TwilioSender()
print(sender.test_connection())
"
```

**Fix**:
- Verify Account SID and Auth Token are correct
- Check Twilio console for account status
- Ensure phone number is properly configured
- Review TWILIO_SETUP_GUIDE.md for complete setup

---

## 🌐 Network & Connectivity Issues

### MCP Server Won't Start
```bash
# Check port availability
lsof -i :8000
# Kill competing processes
pkill -f "uvicorn.*8000"
# Check firewall/security settings
netstat -tlnp | grep 8000
```

### Beeminder API Timeouts
```bash
# Test API connectivity
curl -s "https://www.beeminder.com/api/v1/users/YOUR_USERNAME.json"
# Check rate limits
grep -i "rate" logs/mecris_server.log
```

### External Service Dependencies
```bash
# Verify all external APIs are reachable
ping -c 3 beeminder.com
ping -c 3 api.twilio.com
# Check DNS resolution
nslookup beeminder.com
```

---

## 📁 File System & Permissions

### Obsidian Vault Access
```bash
# Verify vault path exists and is readable
ls -la $OBSIDIAN_VAULT_PATH
# Check permissions
stat -c "%a %n" $OBSIDIAN_VAULT_PATH
# Test file reading
head -5 "$OBSIDIAN_VAULT_PATH/2025-08-06.md"
```

### Database/Config Files
```bash
# Check critical files exist and are writable
ls -la claude_usage.json .env mecris_server.log
# Verify JSON file integrity
python -c "import json; print(json.load(open('claude_usage.json')))"
```

---

## 🔄 Service Recovery Procedures

### Full System Reset
```bash
# Nuclear option - complete restart
pkill -f mecris
pkill -f uvicorn
rm -f mecris_server.log
source venv/bin/activate
python start_server.py
# Wait 10 seconds then test
sleep 10 && curl -s http://localhost:8000/health
```

### Partial Service Recovery
```bash
# Restart only problematic services
# For Twilio issues:
python -c "from twilio_sender import TwilioSender; TwilioSender().test_connection()"
# For Beeminder issues:
curl -s http://localhost:8000/beeminder/status
```

---

## 📝 Logging & Monitoring

### Check Server Logs
```bash
# Real-time log monitoring
tail -f mecris_server.log
# Search for specific errors
grep -i "error\|exception\|fail" mecris_server.log
# Check recent activity
tail -50 mecris_server.log
```

### Debug Mode Activation
```bash
# Start server with enhanced logging
python -m uvicorn mcp_server:app --reload --log-level debug
# Or modify logging in code temporarily
```

---

## 🎯 Performance Issues

### High Response Times
```bash
# Test endpoint performance
time curl -s http://localhost:8000/narrator/context > /dev/null
# Check system resources
top -p $(pgrep -f mecris)
# Monitor database/file I/O
iostat 1 3
```

### Memory Leaks
```bash
# Monitor memory usage over time
ps aux | grep mecris
# Check for growing log files
du -h mecris_server.log
```

---

## 🔐 Security & Access Issues

### Authentication Failures
```bash
# Verify environment variables are loaded
env | grep -E "(BEEMINDER|TWILIO|OBSIDIAN)"
# Check .env file exists and is readable
cat .env | head -5
```

### Permission Denied Errors
```bash
# Fix common permission issues
chmod 644 .env claude_usage.json
chmod 755 venv/bin/activate
# Verify file ownership
ls -la | grep mecris
```

---

## 📈 Test-Specific Debugging

### When pytest Hangs
```bash
# Run with timeout and verbose output
timeout 30s python -m pytest test_mecris_integration.py -v -s
# Run individual test categories
pytest -k "beeminder" -v  # Only Beeminder tests
pytest -k "budget" -v     # Only budget tests
```

### Flaky Test Issues
```bash
# Run tests multiple times to identify patterns
for i in {1..5}; do
    echo "Run $i:"
    python -m pytest test_mecris_integration.py -q
done
```

---

## 🆘 When All Else Fails

### Last Resort Recovery
```bash
# 1. Document the failure state
python -m pytest test_mecris_integration.py > test_failure_$(date +%Y%m%d_%H%M%S).log 2>&1
# 2. Backup current state
cp -r . ../mecris_backup_$(date +%Y%m%d_%H%M%S)
# 3. Clean restart
git status  # Check what's uncommitted
git stash   # Stash any changes
git reset --hard HEAD  # Nuclear reset (CAREFUL!)
# 4. Rebuild
source venv/bin/activate
pip install -r requirements.txt
python start_server.py
```

### Escalation Points
1. **Check TODO.md** - Known issues and current sprint priorities
2. **Review recent git commits** - What changed recently?
3. **Consult MECRIS_SYSTEM_GUIDE.md** - Architecture understanding
4. **Check GitHub Issues** - Community solutions
5. **Document new failure modes** - Update this guide!

---

## 📚 Related Documentation

- **MECRIS_OPERATIONS_GUIDE.md** - Daily operations and startup procedures
- **TESTING_GUIDE.md** - How to run and interpret tests
- **SERVICES_GUIDE.md** - Individual service configurations
- **TODO.md** - Known issues and planned fixes
- **SYSTEM_STATUS.md** - Current system state and known limitations

---

*Last Updated: 2025-08-06 - Based on test suite results showing 5/28 failures*