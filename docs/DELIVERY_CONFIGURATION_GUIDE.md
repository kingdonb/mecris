# Delivery Configuration Guide

> **Mecris Intelligent Reminder System - Production Configuration**

## 🚀 Quick Setup

### 1. Configure Delivery Method
```bash
# In .env file
REMINDER_DELIVERY_METHOD=console    # Start with console for testing
REMINDER_ENABLE_FALLBACK=true       # Enable graceful fallbacks
REMINDER_TEST_MODE=false            # Set to true for testing
```

### 2. Set Up SMS Consent (A2P Compliance)
```bash
# Run once to set up primary user consent
python setup_sms_consent.py
```

### 3. Test the System
```bash
# Test all delivery scenarios
python test_delivery_scenarios.py

# Test live reminder check
curl http://localhost:8000/intelligent-reminder/check

# Test manual trigger
curl -X POST http://localhost:8000/intelligent-reminder/trigger
```

## 📱 Delivery Methods

### Console (Always Works)
```bash
REMINDER_DELIVERY_METHOD=console
```
- **Use for**: Testing, development, SMS not available
- **Output**: Prints messages to console and logs
- **Reliability**: 100% - never fails

### SMS (Production)
```bash
REMINDER_DELIVERY_METHOD=sms
```
- **Requirements**: A2P campaign approved by Twilio
- **Use for**: Production SMS delivery
- **Fallback**: WhatsApp → Console (if enabled)

### WhatsApp (Testing/Personal)
```bash
REMINDER_DELIVERY_METHOD=whatsapp
```
- **Requirements**: Twilio WhatsApp sandbox configured
- **Use for**: Personal testing, international users
- **Fallback**: SMS → Console (if enabled)

### Both (Maximum Reliability)
```bash
REMINDER_DELIVERY_METHOD=both
```
- **Priority**: WhatsApp first, then SMS
- **Use for**: Maximum delivery success rate
- **Fallback**: Console if both fail

## 🔒 A2P Compliance Status

### Current Status
- ✅ **Campaign Submitted**: Personal Reminders / Health & Wellness
- ✅ **Message Samples**: 10 approved samples submitted
- ✅ **Consent System**: Opt-in/opt-out fully implemented
- ✅ **Audit Trail**: All messages logged for compliance
- 🕐 **Approval Pending**: Twilio review in progress

### Production Readiness
```bash
# When A2P campaign is approved:
REMINDER_DELIVERY_METHOD=sms
REMINDER_ENABLE_FALLBACK=true
```

### Compliance Features
- **Opt-in Required**: All users must explicitly consent
- **Message Limits**: Max 3 messages per user per day
- **Time Windows**: Configurable send windows (default 2-5 PM)
- **STOP Support**: Standard Twilio opt-out handling
- **Audit Logs**: 30-day message history for compliance

## 🎯 Configuration Examples

### Development/Testing
```bash
REMINDER_DELIVERY_METHOD=console
REMINDER_TEST_MODE=true
REMINDER_ENABLE_FALLBACK=false
```

### Personal Use (SMS Not Available)
```bash
REMINDER_DELIVERY_METHOD=console
REMINDER_ENABLE_FALLBACK=false
REMINDER_TEST_MODE=false
```

### Production Ready (A2P Approved)
```bash
REMINDER_DELIVERY_METHOD=sms
REMINDER_ENABLE_FALLBACK=true
REMINDER_TEST_MODE=false
```

### Maximum Reliability
```bash
REMINDER_DELIVERY_METHOD=both
REMINDER_ENABLE_FALLBACK=true
REMINDER_TEST_MODE=false
```

## 🛠️ Troubleshooting

### Messages Not Sending
1. **Check consent**: `curl http://localhost:8000/sms-consent/summary`
2. **Check time window**: Messages only sent 2-5 PM by default
3. **Check daily limits**: Max 3 messages per day per user
4. **Check delivery method**: Ensure method is correctly configured

### SMS Delivery Failures
- **A2P Campaign**: Must be approved by Twilio
- **Phone Number**: Must be opted in via consent system
- **Message Content**: Must match approved samples

### Console Fallback Always Working
```bash
# Test console delivery specifically
REMINDER_DELIVERY_METHOD=console python -c "
import requests
print(requests.post('http://localhost:8000/intelligent-reminder/send', 
    json={'message': 'Test', 'type': 'test'}).json())
"
```

## 📊 Monitoring & Analytics

### Consent Status
```bash
curl http://localhost:8000/sms-consent/summary
```

### Delivery Success Rates
- Check logs for delivery method success/failure patterns
- Monitor fallback usage frequency
- Track consent opt-out rates

### Message Frequency
- Daily walk reminders: 1 per day (if needed)
- Budget alerts: Weekly or critical thresholds
- Beeminder emergencies: As needed (max 2/day)

## 🔄 Migration Path

### Phase 1: Console Mode (Complete)
- All messages to console
- Test reminder logic
- Verify consent system

### Phase 2: A2P Approval (Complete)
- Campaign approved by Twilio
- Switch to SMS delivery
- Enable fallbacks

### Phase 3: Multi-User (Complete)
- user_id scoping for all messages
- Isolated budget and goal tracking
- Background workers per user

---

## 🎉 Ready to Deploy

**Current Configuration**: Multi-tenant mode with full A2P compliance
**Next Step**: Implement User-Scoped Secrets API
**Fallback Strategy**: Always graceful degradation to console

The reminder system will **work with $0 Claude budget** and continue functioning even if Twilio delivery fails. Walk accountability is now bulletproof! 🐕🚶‍♂️