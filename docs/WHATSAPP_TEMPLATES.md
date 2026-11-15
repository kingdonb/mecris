# WhatsApp templates: the next catalog (draft for #363)

**Status:** draft for owner review. Nothing here is submitted to Meta, and no
code sends with it yet. WhatsApp is switched off until this catalog is
approved and built (see "Re-enabling" below).

## Why we are starting over

On 2026-11-14 Meta disabled the business portfolio and its WhatsApp Business
Account for "a breach of Terms of Acceptable Use", and the owner requested a
review. Twilio's records:

- 09:59 UTC: the first cloud walk reminder since July was **delivered**.
- Every later send was **undelivered**, with error 63051 (sender locked).
- The sender is OFFLINE, with reason 63112 (the account was disabled by Meta).

Meta did not say which message or behaviour triggered this. These are the
facts we can check against Meta's own template rules
([template guidelines](https://developers.facebook.com/docs/whatsapp/updates-to-pricing/new-template-guidelines)):

1. **One-time codes went out in a utility template.** Phone verification sent
   its code through `mecris_status_v2`. Meta's rule: *only authentication
   templates can send one-time passcodes*.
2. **Our templates were slot-fillers.** `mecris_status_v2` is
   `{{1}} is currently {{2}}. {{3}} is {{4}}. Review {{5}}.` A walk reminder
   rendered as "Daily Walk / NOT FOUND / …". Meta treats unclear or
   placeholder-only content as marketing, and utility templates that are
   really marketing can be recategorized or restricted.
3. **The sending pattern looked unsolicited.** After months of silence, a
   business-initiated message arrived at 04:59, followed by more every two
   hours with no reply from the recipient.

We can't prove any one of these caused the ban. All three are fixable, and the
catalog below is designed so none of them can happen again.

## Principles

1. **Utility means requested and specific.** Every business-initiated template
   answers something the owner set up: a reminder they scheduled, a goal they
   track, a code they requested. No engagement, persuasion or "keep going!"
   copy. Mixed content counts as marketing, so each template carries one
   purpose.
2. **Codes go only in Meta's Authentication template:** copy-code button, no
   URLs, no emoji, parameters of 15 characters or fewer.
3. **Written for a person.** Full sentences, a concrete fact, and one clear next
   step. Variables carry values (numbers, times, goal names), never whole
   phrases, so the fixed text says what the message is.
4. **Reply-gated.** A conversation starts with the owner (opt-in in the app, or
   a message to the number). Once the owner has replied, Mecris talks
   **freeform inside the 24-hour window**, where coaching text needs no
   template. Templates are only for the scheduled reminders the owner asked
   for, and they stop when the owner stops answering (see the send rules).
5. **Quiet and sparse.** These are v0.3.0's gates, applied to every send path:
   the owner's window (14:00–17:59 New York by default), at most 3 messages a
   day, 4 hours apart, nothing at night, and no send while the phone app is
   active.
6. **Delivery is recorded, not assumed.** Store the Twilio message SID and the
   status callback (`queued` → `delivered`/`read`/`undelivered` + error code).
   Stop all sending on an account-level error (63051, 63112).

## The catalog

All existing templates (`*_v1`, `*_v2`) are retired. Names are new, so nothing
is confused with the old set. Example renderings use real-shaped data.

### 1. `mecris_verify_code`: Authentication

Built from Meta's Authentication template library, with a copy-code button.

> *{{1}} is your verification code. For your security, do not share this code.*

- `{{1}}`: 6 digits.
- Sent only when the owner taps VERIFY in the app.
- At most 1 a minute and 5 a day (v0.3.0 already enforces this).

### 2. `mecris_optin_confirm`: Utility (opt-in confirmation)

> *You've turned on Mecris reminders for this number. You'll get at most {{1}}
> a day, between {{2}} and {{3}} ({{4}} time). Reply STOP at any time to turn
> them off.*

Example: *…at most 3 a day, between 2:00 PM and 6:00 PM (New York time)…*

- Sent once, right after the number is verified and reminders are switched
  on in the app.
- This is the only template that goes out without a prior reply, because it
  confirms an opt-in the owner just made.

### 3. `mecris_reminder_due`: Utility (a reminder the owner scheduled)

> *Your {{1}} reminder: {{2}}. Reply DONE when it's done, or LATER and I'll
> check again in a few hours.*

Examples:
- *Your walk reminder: no walk logged yet today, and it's 52°F and dry until
  sunset at 4:41 PM.*
- *Your Arabic reminder: 247 reviews are due, about 60 an hour to clear them
  by 10 PM.*

- `{{1}}`: the reminder name the owner chose (walk, Arabic, Greek…).
- `{{2}}`: one factual sentence built by the renderer (it must pass the rubric).
- This replaces the walk reminder and the daily nag (#349).

### 4. `mecris_goal_deadline`: Utility (account alert)

> *{{1}} is due today: you need {{2}} by {{3}} to stay on track. Reply DONE
> once it's logged.*

Example: *reviewstack is due today: you need 120 reviews by 11:59 PM to stay
on track.*

- Only for Beeminder goals the owner marked "alert me", and only on the day
  the goal is due.

### Freeform (inside the 24-hour window, no template)

After any reply from the owner, Mecris may answer in plain text: coaching,
pace detail, the narrator's line. This is where the "sounds like a coach"
goal from #55 lives. Inside the window, these messages only answer the owner,
so they cannot read as unsolicited.

## Send rules (the reply gate)

```
OFF ── owner verifies + enables reminders ──▶ ARMED (send optin_confirm)
ARMED ── scheduled reminder due, gates pass ──▶ send reminder_due / goal_deadline
any inbound reply ──▶ window open 24 h: freeform allowed, the "unanswered" count resets
2 templates in a row with no reply ──▶ PAUSED (no templates until the owner writes or re-enables)
STOP ──▶ OFF          START ──▶ ARMED
account-level error (63051, 63112) ──▶ OFF everywhere, and the owner is alerted locally
```

- Inbound commands are matched as whole words, case-insensitively: STOP,
  START, DONE, LATER. A YES-style walk acknowledgement must not match
  "yesterday" (v0.3.0 already fixed this for YES).
- "Unanswered" counts templates whose status reached `delivered`, so a send
  that never arrived doesn't count against the owner.

## Rubric (every template and every rendered example)

- [ ] One purpose, stated in the fixed text, not in a variable.
- [ ] Says what happened and what to do next.
- [ ] Concrete values (numbers, times, names); no "NOT FOUND", "EXPECTANT"
      or placeholder words.
- [ ] Reads naturally aloud; no "status is currently".
- [ ] Nothing promotional, persuasive or upselling; no emoji in
      authentication templates.
- [ ] Variables are neither the first nor the last word of the body.
- [ ] Renders correctly with real narrator data through the preview renderer
      (dry run, no send).

## Building it (code work, after this doc is approved)

1. `data/templates/*.json`: bodies, variables and categories in the repo,
   kept in sync from the Twilio Content API (the script is in #378).
2. A preview renderer plus rubric tests, using real narrator data.
3. Store the message SID and delivery status; add a signed StatusCallback
   route in Spin.
4. Reply-gate state per user, and STOP/START/DONE/LATER handling in the
   webhook.
5. One kill switch, `MECRIS_WHATSAPP_ENABLED`, checked by every send path:
   Spin, `send_reminder_message`'s template branch and `smart_send_message`.
6. Submit the four templates for approval and wait for the result.

## Re-enabling (owner decisions)

1. Meta's review either restores the account or upholds the ban. If it is
   upheld, the owner decides whether to register a new sender, under a new
   business portfolio or another provider.
2. The templates are approved, and the code above has shipped.
3. Only then:
   - recreate the `trigger-reminders` cron;
   - set `REMINDER_DELIVERY_METHOD=whatsapp`;
   - verify the number in the app, which sends `mecris_optin_confirm`.

Until then, the phone's local notifications are the reminder channel.
