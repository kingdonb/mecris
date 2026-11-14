# The Key Was Public, and Nobody Could Use It

**Date:** 2026-11-13
**Author:** Claude (Fable 5.2) & Kingdon
**Tags:** [mecris, akamai, spin, twilio, security, cron]
**Status:** draft
**Summary:** A hardcoded API key in a public repo turned out to be the smaller problem. The endpoints it guarded had been refusing their only legitimate callers.

---

Mecris has a cloud half. A Spin app on Akamai Functions is supposed to send walk reminders every two hours and run a sync once a day, so that the system keeps working when the laptop is closed and the phone is asleep. On November 13 we went looking for one security problem in that app and found three, plus a fourth thing that was not a security problem at all.

## The webhook that trusted everyone

When someone replies YES to a walk reminder, Twilio posts the reply to `/internal/twilio-webhook`, and the service logs a walk to Beeminder. The handler began like this:

```rust
let _tok = decrypt_token(&variables::get("twilio_auth_token_encrypted").await?).await?;
```

The underscore is the whole story. The token was fetched, decrypted and never used. Twilio signs every request with that token and sends the result in `X-Twilio-Signature`; nothing checked it. Anyone who knew a user's phone number could post a form containing the word YES and log a walk on their behalf. The `hmac` and `sha1` crates were already in `Cargo.toml`, also unused. Somebody had meant to finish this.

The handler also looked for YES anywhere in the raw request, not in the message text. A reply of "no" from a WhatsApp profile named Yesenia would have counted.

The fix verifies the signature in constant time, fails closed when the token or URL is missing, and reads only the `Body` field. Twilio publishes a test vector for its signing scheme, and it is in the test suite.

## The key in the deploy script

Two other endpoints, `/internal/trigger-reminders` and `/internal/failover-sync`, were guarded by a shared key. Both deploy scripts set it like this:

```bash
--variable internal_api_key="test-internal-key" \
```

The repository is public. The architecture document already listed this as a known gap, and an earlier post on this blog printed the same line in a code sample. And if the variable was ever unset, the check allowed every request.

That is a real finding, and the fix is unsurprising: the key now comes from `.env`, an unset key authorizes nobody, and the service refuses `test-internal-key` permanently, even if a future deploy passes it again.

## The part where it gets strange

Before changing how a key is checked, it is worth finding out who presents it. So we looked for the callers.

There are two. The first is Akamai's platform cron:

```
| failover-sync-edt | /internal/failover-sync     | 5 4 * * *   |
| failover-sync-est | /internal/failover-sync     | 5 5 * * *   |
| trigger-reminders | /internal/trigger-reminders | 0 */2 * * * |
```

`spin aka cron create` accepts a schedule and a path with a query string. It has no option for a header. The service accepted the key only in a header.

The second caller is the Android app, which triggers reminders when it notices the home server has gone dark. It sent no credentials at all.

A request to the live endpoint with no header returns 401. So the key that anyone on the internet could read was a key that neither legitimate caller could present. The scheduled jobs fired on time, every time, and were turned away at the door.

We cannot tell from here how long that has been true. What we can say is how it stayed hidden. The July post that fixed cloud authentication ended with a verification table, and one row read:

| Route | Auth | Status |
|-------|------|--------|
| `POST /internal/failover-sync` | x-internal-api-key | 200 |

That row was honest. A person with `curl` can send a header. The check passed for the one caller who was testing it and for nobody who depended on it.

## What changed

- The internal endpoints accept the key in a header or in a `key` query parameter, because the query string is the only channel platform cron offers. A secret in a URL can end up in request logs. We decided that was acceptable for a key that guards two debounced, opt-in triggers, and wrote the trade-off down.
- A signed-in user's bearer token is also accepted, so the Android app authenticates as the person holding the phone.
- The cron setup script had been creating a job for an endpoint that requires a user token. It now creates the jobs that exist.

## What we are taking from it

**Test as the caller, not as yourself.** The verification in July proved the endpoint could be reached. It did not prove that cron could reach it. The useful question is never "does this return 200" but "does this return 200 for the thing that will call it at four in the morning."

**A scheduler reporting success means it sent a request.** Every one of those jobs ran. Mecris has a rule that cloud functions must record their decisions in the database, including the decision to do nothing, so that silence can be told apart from failure. A request refused by the router never reaches the code that would write that record. The rule needs to cover the door as well as the room.

**Secure and broken can look the same from outside.** Whenever that key was set, the reminder endpoint was, in practice, impossible to abuse. It was also impossible to use.
