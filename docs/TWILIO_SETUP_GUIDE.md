# Twilio Setup and Testing Guide

> **SMS and WhatsApp alerts for Mecris budget and goal emergencies**

## Overview

Mecris uses Twilio to send critical alerts when:
- **Budget is running low** (< 2 days remaining)
- **Beeminder goals are at risk** (derailment imminent)
- **System emergencies** require immediate attention

The system supports both **SMS** (reliable) and **WhatsApp** (rich messaging) delivery.

## Quick Setup

### 1. Get Twilio Credentials
1. Sign up at https://www.twilio.com/try-twilio
2. Get your free trial credits ($15-20 typical)
3. Note your **Account SID** and **Auth Token** from the console
4. Get a **Twilio phone number** (or use trial number)

### 2. Configure Environment Variables
Add these to your `.env` file in the Mecris directory:

```bash
# Required for SMS
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+1234567890  # Your Twilio number
TWILIO_TO_NUMBER=+1987654321    # Your phone number

# Optional for WhatsApp (uses sandbox by default)
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

### 3. Test Your Setup
```bash
# Run all tests
./test_twilio.sh

# Or run interactively
./test_twilio.sh interactive
```

## What Gets Tested

The test script verifies:

1. **Environment Configuration** ✅
   - All required variables present
   - Credentials format correct

2. **SMS Functionality** 📱
   - Basic SMS sending
   - Message delivery confirmation

3. **WhatsApp Functionality** 💬
   - WhatsApp message sending
   - Sandbox integration (if configured)

4. **Budget Alert System** 🚨
   - Budget warning messages
   - Emergency notification format

5. **MCP Integration** 🔌
   - Server endpoint connectivity
   - Alert trigger mechanisms

## WhatsApp Sandbox Setup (Optional)

For WhatsApp testing, you may need to join Twilio's sandbox:

1. **Send Join Message**: Text `join <sandbox-code>` to `+1 (415) 523-8886`
2. **Get Sandbox Code**: Found in Twilio Console → Messaging → Try it out → Send a WhatsApp message
3. **Verify Connection**: Your number is now linked to the sandbox

## Test Script Usage

### Basic Testing
```bash
# Test everything automatically
./test_twilio.sh

# See detailed help
./test_twilio.sh --help
```

### Interactive Mode
```bash
./test_twilio.sh interactive
```

Interactive mode lets you:
- Send individual test messages
- Try custom message content
- Test specific functionality
- Verify delivery without automation

### Example Output
```
🧪 Mecris Twilio Test Suite
==========================

📋 Checking environment variables...
✅ All required environment variables are set
   Account SID: ACa1b2c3...
   From Number: +15551234567
   To Number: +15559876543

📱 Testing SMS functionality...
Sending test SMS: '🧠 Mecris SMS Test - 14:32:15'
✅ SMS sent successfully!

💬 Testing WhatsApp functionality...
Sending test WhatsApp message: '🧠 Mecris WhatsApp Test - 14:32:16'
✅ WhatsApp message sent successfully!

📊 Test Results:
   Passed: 4/4
🎉 All tests passed!
```

## Integration with Mecris

### Automatic Alerts

**Budget Alerts** trigger when:
```bash
# Test budget alert manually
curl -X POST http://localhost:8000/usage/alert
```

**Beeminder Alerts** trigger when:
```bash
# Test beeminder emergency alert
curl -X POST http://localhost:8000/beeminder/alert
```

### Message Types

**Budget Warning**:
```
🚨 CRITICAL: Claude Credits Low

$2.50 remaining
$1.25/day burn rate
~2.0 days left

Time to wrap up or top up.
```

**Beeminder Emergency**:
```
🚨 BEEMERGENCY: 2 goals need immediate attention!
• arabiya: Derails in 2 days
• coding: Due today at 11:59 PM
```

### Message Preferences

- **SMS**: More reliable, works on any phone, costs ~$0.01/message
- **WhatsApp**: Rich formatting, free in sandbox, requires setup

The system tries WhatsApp first, falls back to SMS if needed.

## Troubleshooting

### Common Issues

**"Missing environment variables"**
- Check your `.env` file has all required TWILIO_* variables
- Restart the MCP server after adding variables

**"Failed to send SMS"**
- Verify your Twilio account has credits
- Check that phone numbers include country code (+1)
- Ensure FROM number is a valid Twilio number

**"WhatsApp message failed"**
- WhatsApp requires sandbox join (see setup above)
- Try SMS mode instead for testing
- Check that TO number includes `whatsapp:` prefix

**"MCP endpoints not working"**
- Start the server: `./scripts/launch_server.sh`
- Check server health: `curl http://localhost:8000/health`

### Debugging Commands

```bash
# Check environment variables
env | grep TWILIO

# Test basic Python import
python3 -c "from twilio_sender import send_sms; print('Import OK')"

# Check Twilio account status (requires credentials)
python3 -c "
from twilio.rest import Client
import os
client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
account = client.api.accounts(os.getenv('TWILIO_ACCOUNT_SID')).fetch()
print(f'Account status: {account.status}')
"
```

## Security Notes

- **Never commit** `.env` file to git (it's already in `.gitignore`)
- **Use trial credits** for testing (avoid unexpected charges)
- **Sandbox mode** is free for development
- **Production setup** requires paid Twilio account

## Cost Considerations

- **Trial Account**: $15-20 free credits
- **SMS**: ~$0.01 per message in US
- **WhatsApp**: Free in sandbox, ~$0.005 per message in production
- **Phone Number**: ~$1/month for dedicated number

For budget-conscious testing, use WhatsApp sandbox mode and limit test messages.

---

**Ready to test?** Run `./test_twilio.sh` and follow the prompts!