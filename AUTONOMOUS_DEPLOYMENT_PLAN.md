# 🤖 Autonomous Deployment & Nagging System Implementation Plan

## 🎯 Mission
Deploy a complete autonomous nagging system on ephemeral AWS EC2 infrastructure that can:
- Boot fresh daily from user_data script  
- Clone mecris repo and establish full narrator context
- Run intelligent health checks and send SMS notifications
- Operate autonomously within 5-hour daily window
- Destroy gracefully with no persistent state requirements

## 🏗️ Architecture Overview

```
EC2 t4g.small (Dublin) → user_data script → mecris + claude-code → cron scheduler → SMS alerts
    ↓                         ↓                    ↓                    ↓             ↓
5hr lifespan            fresh clone         MCP context        heuristic engine   Twilio SMS
```

## 📦 Core Components Required

### 1. **Mecris MCP Server Stack**
- **FastAPI server** with narrator context endpoint
- **Beeminder integration** (live API calls)
- **Budget tracking** (local session state only)
- **Twilio SMS client** (outbound notifications)

### 2. **Claude Code CLI Environment**
- **Claude API access** (sonnet-4 model)
- **MCP client configuration** pointing to localhost:8000
- **Venv with all dependencies** (mecris + claude-code requirements)

### 3. **Autonomous Scheduler System**
- **Cron-based health checker** (every 30-60 minutes during 5hr window)
- **Heuristic decision engine** (when to nag, what to say)
- **SMS notification pipeline** (Twilio integration)
- **Session logging** (stdout/files, no persistence needed)

## 🔧 Implementation Components

### A. **User Data Bootstrap Script** 
*Runs once at EC2 launch - installs everything*

**Core Responsibilities:**
- Install Python 3.11+, git, curl, cron
- Clone mecris repo from GitHub (public, no auth needed)
- Create venv and install all requirements
- Install Claude Code CLI (latest stable)
- Configure environment variables from EC2 instance metadata/secrets
- Start MCP server as background daemon
- Configure cron jobs for autonomous checking
- Initialize first health check immediately after boot

**Key Files to Create:**
- `/opt/mecris-deploy/bootstrap.sh` - Main user_data script
- `/opt/mecris-deploy/requirements.txt` - All Python dependencies
- `/opt/mecris-deploy/systemd-services/` - MCP server daemon config
- `/opt/mecris-deploy/cron-jobs/` - Scheduled task definitions

### B. **MCP Server Daemon Configuration**
*Background service providing narrator context*

**Service Requirements:**
- Run MCP server on localhost:8000
- Auto-restart if crashes (systemd supervision)
- Load secrets from instance metadata or environment
- Provide all existing endpoints: `/narrator/context`, `/beeminder/status`, `/usage`, `/beeminder/alert`
- Log to systemd journal (viewable via journalctl, auto-cleaned on destroy)

**Configuration Files:**
- `mecris-mcp.service` - systemd service definition
- `mecris-config.json` - MCP server configuration
- Environment variable template for secrets injection

### C. **Autonomous Health Checker**
*Cron job that runs Claude Code sessions programmatically*

**Core Logic:**
```bash
# Every 45 minutes during operational window
0,45 * * * * /opt/mecris-deploy/health-check.sh
```

**Health Check Script Responsibilities:**
- Activate mecris venv
- Run `claude-code` in batch mode with predefined prompt
- Parse narrator context for urgent items and beemergencies  
- Apply heuristic rules to determine if SMS is warranted
- Send Twilio SMS if action required
- Log all activity to rotating log files

**Heuristic Decision Engine:**
- **Beemergency Detection**: Any Beeminder goal in red/orange → immediate SMS
- **Daily Activity Missing**: No bike/walk data today + afternoon hours → reminder SMS  
- **Budget Warnings**: <5 days remaining budget → conservation mode SMS
- **Goal Deadline Proximity**: High-priority goals due within 48hrs → focus SMS
- **Smart Frequency**: Limit SMS to max 3/day, escalating urgency only

### D. **Claude Code Integration Layer**
*Programmatic interface to run narrator sessions*

**Batch Mode Operation:**
- Configure Claude Code for non-interactive use
- Pre-written prompts for common health check scenarios
- JSON output mode for parsing by health checker script  
- MCP client configuration pointing to localhost:8000
- Budget-conscious model selection (prefer claude-3-5-sonnet over claude-4)

**Key Prompt Templates:**
- `status-check.txt` - Daily health and goal assessment
- `beemergency-triage.txt` - Urgent goal evaluation
- `budget-advisory.txt` - Spending and time management guidance
- `focus-recommendation.txt` - Task prioritization based on context

### E. **Secrets and Configuration Management**
*Secure handling of API credentials without persistence*

**Secrets Required:**
- `BEEMINDER_API_TOKEN` - Live goal data access
- `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` - SMS sending
- `ANTHROPIC_API_KEY` - Claude Code access
- `PHONE_NUMBER` - Target for SMS notifications

**Delivery Methods (choose one):**
- **EC2 Instance Metadata** (user data secrets)
- **AWS Systems Manager Parameter Store** (requires IAM role)
- **Environment variables in user_data** (simplest, least secure)

**Security Considerations:**
- Secrets only in memory during 5hr session
- No secrets written to persistent storage
- Instance termination purges all credential traces

### F. **Session Lifecycle Management**
*Graceful startup and shutdown procedures*

**Boot Sequence:**
1. user_data script runs → install everything
2. Start MCP server daemon → verify localhost:8000 responds
3. Run initial health check → send "daily session started" SMS
4. Enable cron scheduling → autonomous operation begins
5. Set termination handler → "session ending" SMS at 11:55 Eastern

**Shutdown Sequence:**
1. Final health check and status SMS
2. Push any uncommitted work (if applicable)
3. Clean shutdown of MCP server
4. Instance termination (AWS handles this)

## 🚧 Implementation Steps

### Phase 1: Local Development (Week 1)
1. **Create user_data bootstrap script template**
2. **Develop autonomous health checker logic locally**
3. **Test Claude Code batch mode integration**  
4. **Design heuristic decision rules for SMS triggers**
5. **Create systemd service configs for MCP daemon**

### Phase 2: AWS Integration (Week 2)  
1. **Configure EC2 launch template with user_data script**
2. **Test secrets delivery mechanism (metadata vs SSM)**
3. **Validate MCP server auto-start and health endpoints**
4. **Test Claude Code CLI installation and MCP client config**
5. **Verify Twilio SMS sending from EC2 environment**

### Phase 3: Autonomous Operation (Week 3)
1. **Deploy full system and monitor first 5-hour session**
2. **Tune heuristic rules based on actual SMS patterns**
3. **Optimize cron frequency and batch processing**
4. **Implement smart notification throttling**
5. **Add session logging and debugging capabilities**

## 📊 Success Criteria

**Technical Validation:**
- [ ] EC2 instance boots cleanly from user_data script
- [ ] MCP server starts and serves narrator context within 5 minutes
- [ ] Claude Code CLI can connect to MCP and generate status reports
- [ ] Cron jobs execute health checks every 45 minutes
- [ ] SMS notifications sent appropriately based on heuristics
- [ ] Clean shutdown and termination at end of session

**Behavioral Validation:**
- [ ] You receive relevant SMS notifications about goals/budget
- [ ] SMS frequency is appropriate (not spammy, not too rare)
- [ ] Notification content is actionable and contextually aware
- [ ] System operates autonomously without manual intervention
- [ ] Budget consumption stays within daily limits

## ⚠️ Risk Mitigation

**Boot Failures:**
- Comprehensive error handling in user_data script
- Fallback SMS notification if MCP server fails to start
- CloudWatch logs for debugging bootstrap issues

**API Rate Limits:**
- Beeminder: Max 1 request per health check (45min intervals)
- Claude API: Batch operations, prefer cheaper models
- Twilio: Smart throttling, max 3 SMS/day

**Budget Overrun:**
- Monitor token usage in each health check
- Automatic degradation to simpler prompts if budget low
- Emergency cutoff if daily spend exceeds threshold

**SMS Spam Prevention:**
- Exponential backoff for repeated similar alerts
- Daily and weekly SMS limits with smart prioritization
- "Do not disturb" hours configuration

## 🔮 Future Enhancements

**Week 4+:**
- Web dashboard for session monitoring (optional)
- Two-way SMS responses (requires webhook infrastructure)
- Goal completion detection and celebration SMS
- Integration with calendar for context-aware scheduling
- Multi-goal priority balancing algorithms

---

**Next Action**: Begin Phase 1 implementation — create the user_data bootstrap script and test local autonomous health checking logic.