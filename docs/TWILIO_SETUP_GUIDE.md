---
title: "Twilio Setup and Testing Guide"
description: "How Mecris sends WhatsApp template messages through Twilio, and how to test it without sending."
tags: ["twilio", "whatsapp", "setup", "guide"]
date: "2026-11-14"
---

# Twilio Setup and Testing Guide

> **WhatsApp template messages for walk reminders, beemergencies and phone verification. SMS is off.**

## Overview

Mecris talks to you through **WhatsApp template messages** sent by Twilio. A business-initiated WhatsApp message must use a template that Meta has approved, so every send names a Content SID and fills its numbered slots (`{{1}}` to `{{n}}`); there is no free-form body outside the 24-hour reply window.

**SMS is off.** `send_sms` in `twilio_sender.py` is a disabled no-op, and nothing in this guide turns it back on.

Two arms can send:
- **Spin (cloud, `mecris-go-spin/sync-service`)**: walk reminders from the `trigger-reminders` cron and phone-verification codes. From v0.3.0 cloud WhatsApp is a **fallback**: Spin stands down while the phone's heartbeat is younger than `reminder_standdown_minutes` (default 240), sends only from 14:00 to 17:59 America/New_York, at most 3 a day, and never within 4 hours of another nag. The cron is paused until v0.3.0 deploys (#369).
- **Python MCP server**: reminder and alert paths in `twilio_sender.py`, `services/reminder_service.py` and `mcp_server.py`.

Every send is logged in the Neon `message_log` table, scoped by `user_id`. Message content and error text are encrypted (the Python arm still falls back to plaintext when `MASTER_ENCRYPTION_KEY` is missing, see #358). Spin records a Twilio failure as its HTTP status and numeric error code only.

## Setup

### 1. Credentials

Add these to `.env` (never commit it; it is in `.gitignore`):

```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_FROM=whatsapp:+1XXXXXXXXXX   # your approved WhatsApp sender
# Optional override of the mecris_status_v2 Content SID used by Spin
TWILIO_STATUS_TEMPLATE_SID=
# Exact webhook URL configured in the Twilio console, used to check X-Twilio-Signature
TWILIO_WEBHOOK_URL=
```

The recipient is the phone number in your profile, stored encrypted in Neon and verified once from the app (VERIFY, then the WhatsApp code). `TWILIO_TO_NUMBER` is only a local fallback for the Python arm. The Spin variables are pushed from `.env` by `mecris-go-spin/sync-service/deploy-akamai.sh`; see `mecris-go-spin/DEPLOYMENT.md`.

### 2. Templates

- **Approved templates**: `data/approved_templates.json` maps each approved Content SID to its name.
- **Key template**: `mecris_status_v2` (`HX9403f1b85350b8c05780a1128b79f3c2`) carries walk reminders and verification codes. Senders fill 5 slots (`slots()` in `mecris-go-spin/sync-service/src/lib.rs`).
- **Approved bodies**: `scripts/fetch_template_bodies.py` reads each approved SID's body, sample variables, category and approval status from the Twilio Content API (GET only) and writes `data/templates/<name>.json`. It needs your credentials and your OK; `--dry-run` writes nothing. Once the bodies are committed, `tests/test_template_catalog.py` checks that every approved SID has a body and that `mecris_status_v2` has the 5 slots the senders fill (#363).
- **Template categories**: Meta's current guidelines are at <https://developers.facebook.com/docs/whatsapp/updates-to-pricing/new-template-guidelines>. An archived copy of an older version is in `attic/docs/template_category_guidelines.pdf`.

## Testing without sending

The test suite never sends a real message and needs no `.env`:

```bash
.venv/bin/python -m pytest -q tests/test_twilio_sender.py tests/test_sms_mock.py \
  tests/test_fetch_template_bodies.py tests/test_pii_log_hygiene.py
cd mecris-go-spin/sync-service && cargo test
```

For the deployed Spin API, run `./scripts/verify_spin_deploy.sh` after each deploy. Read its usage line first: it must not make a real `trigger-reminders` call inside the window (see `docs/RELEASE_PROCESS.md`, section 8b).

Use Twilio's magic test numbers (`+1500555xxxx`) in tests and examples, never a real number. `tests/test_no_personal_numbers.py` fails CI if a tracked file holds a phone number that is not a test, fiction or allowlisted business number.

The old live test script (`test_twilio.sh`) is retired to `attic/tests/`: it sent real SMS and WhatsApp messages and imported functions that no longer exist.

## Debugging delivery

If Twilio accepted a message (`201 Created`) but nothing arrived:

1. Look up the message by SID in the Twilio console (Monitor, Logs, Messaging), or check its status with the Twilio CLI. Do not paste recipients or message bodies into issues or logs.
2. Common error codes:
   - **63049**: invalid Content SID, or the template is not approved for this sender.
   - **63016**: outside the 24-hour window and not sent as an approved template.
   - **63015**: the recipient has not joined the sandbox (sandbox senders only).

`scripts/debug_twilio_messages.py` prints recipients and message bodies; treat its output as private.

### Inbound replies

Replies reach `/internal/twilio-webhook` on the Spin API, which rejects requests without a valid `X-Twilio-Signature` (403). If replies are refused after a URL change, set `TWILIO_WEBHOOK_URL` to the exact URL configured in the Twilio console and redeploy.

## Security notes

- Never commit `.env`, a personal phone number or a message body. Log Twilio failures by status and numeric code only.
- `INTERNAL_API_KEY` guards the Spin `/internal/*` endpoints. Akamai cron passes it in the query string, so `spin aka cron list` output must never be pasted anywhere.
- The Twilio sandbox (`whatsapp:+14155238886`) is for development only; production uses the approved business sender.
