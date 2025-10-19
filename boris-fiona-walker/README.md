# 🐕 Boris & Fiona Walk Reminder

A WASM-based walk reminder system deployed on Spin Cloud that sends SMS reminders to Kingdon when it's time to walk Boris and Fiona.

## Architecture

```
GitHub Actions Cron → Spin Cloud WASM → Twilio SMS
       ↓                     ↓              ↓
   (free tier)          (free tier)    ($0.0075/SMS)
   Hourly 2-6 PM       Instant exec    Direct to phone
```

## Features

- **Time-aware reminders**: Only sends reminders between 2-6 PM Eastern
- **Rate limiting**: Maximum one reminder per day
- **Weather-aware messages**: Different messages for different times of day
- **Zero server costs**: Runs on Spin Cloud free tier
- **Instant cold start**: WASM module starts in milliseconds

## Message Examples

- **Afternoon (2-3 PM)**: "🐕 Afternoon walk time! Boris and Fiona are ready for their adventure."
- **Golden Hour (4-5 PM)**: "🌅 Golden hour walk! Boris and Fiona would love a sunset stroll."
- **Evening (6 PM)**: "🌆 Evening walk time! Boris and Fiona are waiting by the door."

## Development

### Prerequisites

- [Spin CLI](https://developer.fermyon.com/spin/install) installed
- Rust toolchain with `wasm32-wasi` target
- Twilio account with SMS capabilities

### Local Development

```bash
# Install wasm32-wasi target
rustup target add wasm32-wasi

# Build the WASM module
spin build

# Run locally (requires environment variables)
spin up

# Test the endpoint
curl -X POST http://localhost:3000/check
```

### Environment Variables

Set these in Spin Cloud or your local environment:

```bash
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token  
TWILIO_FROM_NUMBER=+1234567890
TWILIO_TO_NUMBER=+1234567890
```

### Deployment

```bash
# Deploy to Spin Cloud
spin deploy

# The app will be available at:
# https://boris-fiona-walker-xxx.fermyon.app/check
```

## GitHub Actions

The workflow runs every hour from 2-6 PM Eastern and calls the WASM endpoint. Set the `SPIN_APP_URL` secret in your GitHub repository to your deployed Spin Cloud app URL.

## Cost Estimate

- **Spin Cloud**: Free tier (1000 requests/day)
- **GitHub Actions**: Free tier (2000 minutes/month)  
- **Twilio SMS**: $0.0075 per message
- **Total**: ~$2.25/month for daily reminders

## Testing

```bash
# Run unit tests
cargo test

# Test deployment locally
spin up
curl -X POST http://localhost:3000/check
```

## Project Structure

```
boris-fiona-walker/
├── spin.toml                 # Spin app configuration
├── Cargo.toml               # Rust dependencies
├── src/
│   ├── lib.rs              # Main HTTP handler
│   ├── sms.rs              # Twilio SMS integration
│   └── time.rs             # Eastern timezone utilities
├── .github/workflows/
│   └── walk-reminder-cron.yml  # Hourly cron job
└── README.md
```

## Contributing

This is part of the larger Mecris autonomous SMS accountability system. See the main repository for contribution guidelines and project roadmap.

---

Built with ❤️ for Boris and Fiona 🐕🐕