# 🔄 Mecris Control Loop Specification

> **Self-Managing AI Framework for Time-Bucketed Iteration with Budget Awareness**

## 🎯 Vision

Mecris implements a **self-managing AI control loop** where Claude monitors its own progress, manages API budget, and makes autonomous decisions about when to work, when to alert the human, and when to pause - all within strict financial constraints and time windows.

This is not just task automation - it's **meta-cognitive resource management** with real financial stakes.

---

## 💰 Budget Framework

### Financial Constraints
- **Total Budget:** $24.02 Claude API credits (expires August 5, 2025)
- **Daily Target:** $3-5/day burn rate (efficient with budget buffer)
- **Runtime:** ~1.5 days remaining
- **Risk Tolerance:** Willing to forfeit $3 to maximize value extraction
- **Current Status:** $13.92 remaining (real balance from manual update)

### Budget Tracking Architecture

**Two-Source System:**
1. **Local Estimates:** Token-based "checkbook" tracking for session-to-session
2. **Manual Reconciliation:** Periodic updates from Anthropic Console balance

**Reconciliation Process:**
1. Mecris writes "checks" against estimated balance using token costs
2. User manually checks Anthropic Console (daily/weekly)
3. User runs `./update_budget.sh <actual_remaining> <actual_total>`
4. System reconciles discrepancies and adjusts future estimates
5. Control loop uses reconciled balance for decision making

**Security Considerations:**
- No stored Anthropic credentials (manual console checks only)
- Infrequent balance queries to avoid ToS violations
- User maintains full control of account access

### Budget States
- **NORMAL:** < $5/day, continue planned work
- **ACCELERATE:** > $5/day acceptable if high-value work detected
- **PRESERVE:** Near daily limit, switch to planning/documentation
- **EMERGENCY:** Critical budget threshold, halt non-essential operations

---

## ⏰ Time-Bucketed Architecture

### Session Concept
- **Session Duration:** 5-hour rate-limit reset periods (Claude Code Monitor concept)
- **Ping Frequency:** Multiple pings per day until daily budget consumed
- **State Persistence:** Each session resumes from previous state via MCP data

### Ping-Driven Lifecycle
```
Ping Received → Context Assessment → Decision → Action → State Update → Sleep
     ↑                                                                    ↓
     ←←←←←←←←←←←←←←← Budget Available? ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
```

---

## 🧠 Decision Heuristics

### Primary Decision Matrix
Each ping triggers evaluation of:

1. **CONTINUE WORKING** ✅
   - Budget available for current day
   - Active todos in progress
   - No critical external alerts
   - Previous session showed progress

2. **SEND TWILIO ALERT** 📱
   - Beeminder emergency detected
   - Budget threshold crossed
   - Unexpected error states
   - Major milestone reached
   - User intervention needed

3. **PAUSE/PLAN** ⏸️
   - Daily budget exhausted
   - No clear high-value tasks
   - Waiting for external dependencies
   - System health issues

4. **DEEP WORK MODE** 🚀
   - High-value opportunity detected
   - Clear path to completion
   - Budget allows acceleration
   - User gave "churn until done" signal

### Context Sources for Decision Making
- **Local Budget Tracker:** Token-based cost estimates, checkbook-style tracking
- **Manual Budget Updates:** Periodic reconciliation with Anthropic Console balance
- **Beeminder:** Goal derailment risks, emergency states
- **Obsidian:** Current todos, progress notes, user instructions
- **System State:** MCP health, error logs, completion rates

---

## 🔌 MCP Integration Points

### Required MCP Servers
1. **Local Budget Tracking** (IMPLEMENTED - Primary Budget Source)
   - Token-based cost estimation ("checkbook" tracking)
   - Local SQLite database persistence
   - Manual reconciliation with Anthropic Console
   - Infrequent scraping to avoid ToS violations

2. **Obsidian MCP** (IMPLEMENTED)
   - Progress notes
   - Todo management
   - User instruction updates
   - Session logging

3. **Beeminder MCP** (IMPLEMENTED)
   - Goal status monitoring
   - Emergency detection
   - Derailment alerts

4. **Twilio MCP** (IMPLEMENTED)
   - Alert messaging
   - Status updates
   - Emergency notifications

### Data Flow
```
Local Budget Tracker → Estimated Budget State → Decision Engine → Action
                                                       ↓
Manual Console Update → Reconciliation → Updated Budget State
                                                       ↓
Beeminder → Emergency State → Decision Engine → Twilio Alert
                                                       ↓
Obsidian → Progress State → Decision Engine → Continue/Pause
```

---

## 📊 Progress Monitoring Framework

### Self-Monitoring Metrics
- **Financial Efficiency:** Value delivered per dollar spent
- **Task Completion Rate:** Todos completed per session
- **Alert Accuracy:** Relevant vs. false positive alerts
- **Budget Adherence:** Actual vs. planned spend
- **Goal Alignment:** Progress toward user objectives

### Progress Persistence
- **Session Logs:** Detailed work summaries in Obsidian
- **State Snapshots:** Current context preserved between pings
- **Decision History:** Why each ping resulted in specific action
- **Budget Timeline:** Spend pattern analysis

---

## 🎛️ Control Parameters

### Adjustable Thresholds
```yaml
budget:
  daily_target: 3.00        # USD per day
  emergency_threshold: 0.50  # USD remaining triggers pause
  acceleration_limit: 5.00   # Max daily spend for urgent work

timing:
  ping_interval: 3600       # Seconds between pings
  session_timeout: 14400    # Max session duration (4 hours)
  planning_buffer: 1800     # Time reserved for session wrap-up

decision_weights:
  beeminder_urgency: 0.4    # How much beemergencies influence decisions
  budget_pressure: 0.3      # How much budget affects work intensity
  progress_momentum: 0.3    # How much current progress affects continuation
```

---

## 🔍 Implementation Strategy

### Phase 1: Infrastructure (Current)
- ✅ Basic MCP servers (Obsidian, Beeminder, Twilio)
- ✅ Local budget tracking with token estimation
- ✅ Manual budget reconciliation script
- ⏳ Ping mechanism implementation
- ⏳ Decision engine framework

### Phase 2: Intelligence
- Budget-aware decision making
- Context synthesis from multiple MCPs
- Heuristic refinement based on outcomes
- Self-improvement feedback loops

### Phase 3: Optimization
- Predictive budget modeling
- Dynamic parameter adjustment
- Value optimization algorithms
- Human feedback integration

---

## 🚨 Emergency Protocols

### Budget Exhaustion
1. Send Twilio alert with remaining work summary
2. Create detailed handoff notes in Obsidian
3. Pause all non-critical operations
4. Generate value assessment report

### System Failures
1. Fall back to manual Twilio alerts
2. Log failure state in session log
3. Attempt graceful degradation
4. Request human intervention if critical

### Beeminder Emergencies
1. Immediate Twilio alert with goal details
2. Interrupt current work if necessary
3. Provide specific action recommendations
4. Monitor for resolution

---

## 📈 Success Metrics

### Primary KPIs
- **Value Extraction:** Maximize utility from $24 budget
- **Goal Achievement:** Complete critical objectives before August 5
- **System Reliability:** Minimize downtime and false alerts
- **Efficiency:** Optimize cost per meaningful outcome

### Secondary Metrics
- Session success rate
- Alert response time
- Budget variance
- User satisfaction indicators

---

## 🎮 User Interface

### Human Control Points
- **"Churn until done" signal:** Override budget constraints for critical work
- **Parameter adjustment:** Modify control parameters via Obsidian notes
- **Emergency override:** Twilio-based system pause/resume
- **Progress review:** Periodic check-ins via session logs

### Transparency Guarantees
- All decisions logged with reasoning
- Budget spend tracked in real-time
- Progress visible in Obsidian vault
- Alert history maintained

---

**This framework transforms Claude from a reactive assistant into a proactive, budget-aware cognitive partner that operates autonomously within defined constraints while maintaining full transparency and human oversight.**

*Next: Implement Claude Code Monitor MCP integration and test the first ping cycle.*