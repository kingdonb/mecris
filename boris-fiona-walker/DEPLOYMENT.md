# 🚀 Spin Cloud Deployment Guide

This guide covers deploying the Boris & Fiona Walk Reminder system to Spin Cloud for production use.

## 📋 Pre-Deployment Checklist

### **✅ Development Ready**
- [x] WASM component builds successfully (`make build`)
- [x] All tests passing (`make test` - 22/22 tests ✅)
- [x] Local development working (`make dev`)
- [x] API endpoints responding correctly
- [x] Web frontend displaying properly

### **🔑 Production Credentials Required**
Before deploying to production, update `.envrc` with real credentials:

```bash
# Edit .envrc with real values
nano .envrc

# Required changes:
export SPIN_VARIABLE_TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Real Twilio Account SID
export SPIN_VARIABLE_TWILIO_AUTH_TOKEN="your_real_auth_token_here"            # Real Twilio Auth Token  
export SPIN_VARIABLE_TWILIO_FROM_NUMBER="+1234567890"                        # Real Twilio phone number
export SPIN_VARIABLE_TWILIO_TO_NUMBER="+1234567890"                          # Real destination phone

# Optional for weather integration (future):
export SPIN_VARIABLE_OPENWEATHER_API_KEY="your_real_api_key_here"            # Real OpenWeather API key

# Required for deployment:
export SPIN_CLOUD_APP_NAME="boris-fiona-walker"                              # Your chosen app name

# Reload environment
direnv allow
```

## 🚀 Deployment Process

### **Step 1: Prepare for Deployment**
```bash
# Ensure you're logged into Spin Cloud
spin cloud login

# Verify build works
make build

# Run final tests
make test
```

### **Step 2: Deploy to Spin Cloud**
```bash
# Deploy using our Makefile
make deploy

# OR manually:
spin deploy
```

### **Step 3: Configure Environment Variables**
After deployment, set production environment variables in Spin Cloud:

```bash
# Set Twilio credentials
spin cloud variables set TWILIO_ACCOUNT_SID "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
spin cloud variables set TWILIO_AUTH_TOKEN "your_real_auth_token_here"
spin cloud variables set TWILIO_FROM_NUMBER "+1234567890"
spin cloud variables set TWILIO_TO_NUMBER "+1234567890"

# Set weather API key (optional)
spin cloud variables set OPENWEATHER_API_KEY "your_real_api_key_here"
```

### **Step 4: Test Production Deployment**
```bash
# Get your app URL
spin cloud apps info boris-fiona-walker

# Test the API endpoint
curl -X POST https://boris-fiona-walker-xxx.fermyon.app/check

# Test the web frontend
open https://boris-fiona-walker-xxx.fermyon.app/
```

## 🔧 GitHub Actions Integration

### **Current Workflow Location**
The GitHub Actions workflow should be updated to trigger the deployed Spin Cloud app:

```yaml
# .github/workflows/walk-reminder-cron.yml
name: Boris & Fiona Walk Reminder

on:
  schedule:
    # Run every hour from 2-6 PM Eastern (18-22 UTC during EST, 19-23 UTC during EDT)
    - cron: '0 18-22 * * *'  # Adjust for EST/EDT as needed
  workflow_dispatch:  # Allow manual triggering

jobs:
  remind-walk:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Walk Reminder
        run: |
          curl -X POST https://boris-fiona-walker-xxx.fermyon.app/check
```

### **Update Required**
Replace `https://boris-fiona-walker-xxx.fermyon.app` with your actual Spin Cloud app URL after deployment.

## 📊 Production Monitoring

### **Health Checks**
```bash
# Check app status
spin cloud apps info boris-fiona-walker

# View logs
spin cloud logs boris-fiona-walker

# Test endpoints
curl -X POST https://your-app-url.fermyon.app/check
curl https://your-app-url.fermyon.app/
```

### **Key Metrics to Monitor**
- **SMS delivery success rate** (should be >95%)
- **API response times** (should be <500ms)  
- **Daily reminder frequency** (max 1 per day)
- **Error rates** (should be <1%)

## 🎯 Expected Behavior

### **Daily Operation**
1. **GitHub Actions** triggers `/check` endpoint every hour 2-6 PM Eastern
2. **Walk Reminder Logic** checks:
   - Current time (must be 14-18 hours Eastern)
   - Already reminded today (rate limiting)
   - Weather conditions (future feature)
3. **SMS Delivery** sends reminder via Twilio if conditions met
4. **Rate Limiting** prevents duplicate reminders same day

### **Cost Expectations**
- **Spin Cloud Compute**: FREE (within free tier limits)
- **SMS via Twilio**: ~$0.0075 per message = ~$2.25/month for daily reminders
- **Total Monthly Cost**: ~$2.25/month

## 🔍 Troubleshooting

### **Common Issues**

#### **Deployment Fails**
```bash
# Check login status
spin cloud login

# Verify build works locally
make build
make test

# Check app name conflicts
spin cloud apps list
```

#### **SMS Not Sending**
```bash
# Check environment variables are set
spin cloud variables list boris-fiona-walker

# Test Twilio credentials locally first
make watch
make api-test  # Should show detailed error if credentials invalid
```

#### **Wrong Time Zone**
```bash
# Check logs for timezone issues
spin cloud logs boris-fiona-walker

# Verify Eastern timezone logic in tests
make test
```

### **Getting Help**
- **Spin Cloud Docs**: https://developer.fermyon.com/cloud/
- **Twilio Console**: https://console.twilio.com/
- **GitHub Actions**: Check workflow runs for trigger issues

## ⚠️ Production Readiness Status

### **✅ Ready for Production**
- [x] **Code Quality**: 22/22 tests passing, comprehensive coverage
- [x] **Architecture**: Sound WASM + Spin Cloud + Twilio design
- [x] **Development Workflow**: Professional Makefile + direnv setup
- [x] **Documentation**: Complete guides and API documentation
- [x] **Security**: Environment variables properly managed
- [x] **Cost Optimization**: ~$2.25/month target achieved

### **🔑 Waiting for Real Credentials**
- [ ] **Twilio Account SID**: Replace "test" with real value
- [ ] **Twilio Auth Token**: Replace "test" with real value  
- [ ] **Phone Numbers**: Set real from/to numbers
- [ ] **Production Testing**: Verify SMS delivery with real credentials

### **🚀 Ready to Deploy**
Once real credentials are set:
1. Update `.envrc` with real values
2. Run `make deploy`
3. Set Spin Cloud environment variables
4. Update GitHub Actions workflow URL
5. Test end-to-end SMS delivery

**Boris and Fiona are ready for their production walk reminders!** 🐕🐕✨