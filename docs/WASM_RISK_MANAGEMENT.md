# 🛡️ WASM Module Risk Management & Safety Assessment

**Component**: `boris-fiona-walker` (Rust/Spin WASM Module)  
**Date**: March 3, 2026  
**Status**: 🟡 **DEVELOPMENT - SAFETY CONTROLS REQUIRED**

---

## 🔍 **RISK ASSESSMENT: "THE INFINITE SPIN"**

### **The Risk**
A bug in the logic, a misconfigured cron job, or an unhandled API error could cause the WASM module to trigger thousands of times, potentially:
1. **Exhausting Twilio Credits**: Each SMS costs ~$0.0075. An infinite loop could drain account balances rapidly.
2. **Beeminder Data Corruption**: Incorrect automated logging could derail goals or create "ghost" progress.
3. **Spin Cloud Resource Usage**: While on the free tier, excessive requests could lead to account suspension.

### **Current Safety Controls**
The following controls are already implemented in `src/lib.rs`:
- ✅ **Time Windowing**: Logic only executes between 14:00 and 18:00 Eastern.
- ✅ **Date-Based Rate Limiting**: Uses Spin KV store to ensure only one reminder is sent per calendar day.
- ✅ **IP-Based Rate Limiting**: Limits requests to one per hour per IP to prevent external DoS/abuse.
- ✅ **Authentication**: Requires a `Bearer` token (webhook secret) to access the `/check` endpoint.

---

## 🛠️ **PROPOSED SAFETY ENHANCEMENTS**

### 1. **"Dry Run" / "Mock Mode" (Immediate Priority)**
Implement a `MOCK_MODE` environment variable. When `true`, the system will:
- Log the SMS message to `stdout` instead of calling the Twilio API.
- Use a mock Beeminder response instead of calling the live API.
- Allow testing the full "Momentum Pivot" logic without external side effects.

### 2. **Circuit Breaker Pattern**
Implement a "Circuit Breaker" in the Spin KV store:
- If the module detects more than X executions in a 10-minute window, it sets a `SYSTEM_LOCK` key.
- All subsequent requests return `503 Service Unavailable` until the lock is manually cleared.

### 3. **Validation Scaffold**
Before "Real" deployment, we will use a **Validation Scaffold**:
- **Stage 1**: Deploy with `MOCK_MODE=true` and `webhook_secret=test`.
- **Stage 2**: Verify GitHub Actions cron triggers correctly and logs appear in Spin Cloud.
- **Stage 3**: Verify rate limiting correctly blocks the 2nd through 24th hourly triggers.
- **Stage 4**: Promotion to Production (`MOCK_MODE=false`, real secrets).

---

## 📋 **PRE-PROMOTION CHECKLIST**

- [ ] **MOCK_MODE Implementation**: Verified that Twilio calls are bypassed.
- [ ] **Credential Sanitization**: Confirmed no real keys are in `spin.toml` or `Cargo.toml`.
- [ ] **KV Store Persistence**: Verified that rate-limiting state survives across WASM cold starts.
- [ ] **Cost Monitoring**: Twilio "Auto-Top Up" is disabled or set to a low threshold ($20).

---

## 🎯 **CONCLUSION**

The primary risk is **Financial (Twilio)**. By implementing a explicit `MOCK_MODE` and validating the rate-limiting behavior in a live Spin Cloud environment *before* adding real credentials, we eliminate the risk of an "Infinite Spin" burning credits.

**Approval required before Stage 4 promotion.**
