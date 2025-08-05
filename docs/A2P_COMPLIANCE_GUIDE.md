# A2P SMS Campaign Compliance Guide

> **Mecris as a Service - Personal Accountability Automation**  
> *Twilio A2P Campaign Requirements & Implementation*

## 📋 Campaign Details (Submitted to Twilio)

### Business Information
- **Service**: Mecris - Personal Accountability Automation System
- **Domain**: mecris.urmanac.com (future)
- **Business Type**: Sole Proprietorship → SaaS Platform
- **Campaign Type**: Personal Reminders / Health & Wellness

### End-User Consent Protocol

**Consent Flow**:
> End users opt-in by visiting mecris.urmanac.com and creating an account for personal accountability automation. During signup, users provide their phone number and check a clear consent box agreeing to receive SMS reminders from Mecris. The opt-in occurs after users complete account creation and configure their personal goals (Beeminder integration, daily activity tracking, budget monitoring). Users explicitly choose which reminder types to receive (walk reminders, goal alerts, budget warnings) and set their preferred time windows. The web interface includes a prominent SMS preferences section where users can modify or disable messaging at any time. Additionally, users can text START to our number to reactivate messaging if previously disabled. This is a personal productivity service helping individuals stay accountable to their health and goal-tracking commitments through intelligent, context-aware reminders.

### Opt-in Keywords
- `START` - Activate messaging
- `REMIND` - Reactivate reminders  
- `SUBSCRIBE` - Join messaging service
- `JOIN` - Join accountability system

### Opt-in Confirmation Message
```
🧠 Welcome to Mecris! Your personal accountability system is now active. You'll receive smart reminders for walks, goals, and budget alerts. Reply STOP anytime to opt out.
```

### Opt-out Support
- `STOP` - Standard Twilio opt-out (automatically handled)
- `UNSUBSCRIBE` - Alternative opt-out keyword
- Web interface preference toggle
- Customer support contact

## 📱 Approved Message Samples

### Daily Walk Reminders (Most Frequent)
- 🚶‍♂️ Walk reminder - no activity logged today and the dogs need exercise!
- 🐕 Time for that daily walk - your bike goal needs progress and the dogs are giving you the look
- 🚶‍♂️ No walk detected today - time to move! (and the dogs won't stop staring)

### Budget/System Alerts (Weekly-ish)
- 💰 Budget alert: $2.30 remaining. Focus mode activated - wrap up the high-value work
- 🚨 OB Mirror safebuf is 3, expected 8 - server may need attention (kick something?)

### Beeminder Emergencies (Occasionally)
- 🚨 arabiya derails in 2 days - time to practice some Arabic before the pledge hits
- ⚠️ 2 Beeminder goals need attention today - arabiya and coding both getting risky

### Motivational/Strategic (Rare)
- 🎯 Perfect afternoon for progress - bike goal is safe, budget is good, time to tackle that arabiya backlog
- 🧠 System check: All goals safe, walk logged, budget healthy. You're crushing it today.
- 🚶‍♂️ Walk + think time - your best problem-solving happens on foot and the dogs agree

## 🔧 Technical Implementation

### Current Status
- ✅ **Single User Mode**: Currently serving one user (system owner)
- 🚧 **A2P Campaign**: Submitted, awaiting approval
- 🔄 **Delivery System**: Smart fallback (WhatsApp → SMS → Console)
- ✅ **No-Spam Protection**: Max 1 message per type per day

### Configuration Options
```bash
# .env configuration
REMINDER_DELIVERY_METHOD=console  # Options: console, sms, whatsapp, both
REMINDER_ENABLE_FALLBACK=true     # Try alternatives if primary fails
REMINDER_TEST_MODE=false          # Console output instead of delivery
```

### Compliance Features Needed

#### Phase 1: MVP Compliance
- [ ] **Opt-in Web Interface** - Simple signup form with SMS consent
- [ ] **Preference Management** - User dashboard for message types/timing
- [ ] **STOP Keyword Handling** - Enhanced opt-out processing
- [ ] **Message Audit Log** - Track all sends for compliance

#### Phase 2: Full SaaS Compliance  
- [ ] **User Account System** - Authentication and profile management
- [ ] **Billing Integration** - Subscription management
- [ ] **Multi-user Support** - Isolated user contexts
- [ ] **API Rate Limiting** - Prevent abuse and spam

## 🎯 Migration Plan: Single User → SaaS

### Current State (Single User)
```
User configures .env → System sends reminders → Single phone number
```

### Target State (SaaS Platform)
```
User signs up → Configures goals → Consents to SMS → Personalized reminders
```

### Implementation Steps
1. **Web Interface**: Simple signup form with Twilio consent
2. **User Database**: Store preferences and consent status
3. **Message Routing**: Per-user phone numbers and preferences
4. **Compliance Tracking**: Audit logs and opt-out handling

## 📊 Message Frequency Expectations

| Message Type | Frequency | Time Window | Max/Day |
|-------------|-----------|-------------|---------|
| Walk Reminders | Daily (if needed) | 2-5 PM | 1 |
| Budget Alerts | Weekly or critical | 9 AM - 5 PM | 1 |
| Beeminder Emergencies | As needed | 8-9 AM, 6-8 PM | 2 |
| Strategic Messages | Rare | 2-5 PM | 1 |

## 🛡️ Privacy & Security

### Data Handling
- **Phone Numbers**: Encrypted storage, Twilio credentials secured
- **Message Content**: No PII beyond accountability context
- **User Preferences**: Stored locally, user-controlled deletion
- **Audit Trail**: Message logs for compliance, auto-purged after 30 days

### Compliance Boundaries
- **Personal Use Only**: No marketing, no third-party sharing
- **Opt-out Honored**: Immediate cessation of messaging
- **Data Minimization**: Only store what's needed for functionality
- **User Control**: Full preference management and deletion rights

---

## 🚀 Go-Live Checklist

### Pre-Launch
- [ ] A2P Campaign approved
- [ ] Basic web interface deployed
- [ ] User consent flow tested
- [ ] STOP keyword handling verified
- [ ] Message audit logging active

### Launch Ready
- [ ] Single user → Multi-user migration complete
- [ ] Billing system integrated (if paid service)
- [ ] Terms of Service and Privacy Policy published
- [ ] Customer support channel established

**Current Focus**: A2P approval → Console fallback → Web interface → Multi-user support