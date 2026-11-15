# WhatsApp templates: the next catalog (draft for #363)

**Status:** draft. The owner's first review is folded in (2026-11-15). Nothing
here is submitted to Meta, and no code sends with it yet. WhatsApp stays
switched off until Meta's review is decided and this catalog is approved and
built (see "Re-enabling" below).

## Why we are starting over

On 2026-11-14 Meta disabled the business portfolio and its WhatsApp Business
Account for "a breach of Terms of Acceptable Use". The owner has requested a
review. Twilio's records:

- 09:59 UTC: the first cloud walk reminder since July was **delivered**.
- Every later send was **undelivered** with error 63051 (sender locked).
- The sender is OFFLINE with reason 63112 (the account was disabled by Meta).

Meta did not say what triggered the ban. These are the facts we can check
against Meta's own template rules
([template guidelines](https://developers.facebook.com/docs/whatsapp/updates-to-pricing/new-template-guidelines)):

1. **One-time codes went out in a utility template.** Phone verification sent
   its code through `mecris_status_v2`. Meta's rule is that *only
   authentication templates can send one-time passcodes*.
2. **Our templates were slot-fillers.** `mecris_status_v2` is
   `{{1}} is currently {{2}}. {{3}} is {{4}}. Review {{5}}.` A walk reminder
   rendered as "Daily Walk / NOT FOUND / …". Meta treats unclear or
   placeholder-only content as marketing, and it can recategorize or restrict
   utility templates that are really marketing.
3. **The sending pattern looked unsolicited.** After months of silence, a
   business-initiated message arrived at 04:59, then more every two hours with
   no reply.

We can't prove any one of these caused the ban. All three are fixable, and the
catalog below is designed so none of them can happen again.

## Scope: walking only

The Android app's local notifications already handle Arabic and Greek
reviews well. They are not in doubt and they stay where they are. WhatsApp
has one job: **getting the owner out for a walk**. A narrow, clearly requested
purpose is also the easiest case for "utility".

## Principles

1. **Utility means requested and specific.** Every business-initiated template
   answers something the owner set up: the walk reminder they turned on, or a
   code they requested. No engagement, persuasion or "keep going!" copy. One
   purpose per template.
2. **Codes go only in Meta's Authentication template:** a copy-code button,
   no URLs, no emoji, parameters of 15 characters or fewer.
3. **Written for a person.** Full sentences, a concrete fact, and one clear
   next step. Variables carry values (times, step counts), never whole
   phrases, so the fixed text says what the message is. Mecris may say "I": it
   should sound like a helpful assistant, not a status board.
4. **Replies have to be worth sending.** Nobody answers a reminder unless
   answering does something. So every reply word below changes what Mecris
   does next (snooze, start a walk, stop). This is not a chatbot. Richer
   replies are a separate epic (see "Later: conversational replies").
5. **At most 2 reminder templates a day.** Three is already naggy. They go only
   inside the owner's window (14:00–17:59 New York by default; Eastern time is
   assumed throughout, which matches where the owner lives), never at night,
   and never while the phone app shows recent activity.
6. **Delivery is recorded, not assumed.** Store the Twilio message SID and the
   status callback (`queued` → `delivered`/`read`/`undelivered` + error code).
   Stop all sending on an account-level error (63051, 63112).

## The catalog

All 14 existing templates (`*_v1`, `*_v2`) are retired. The new names avoid
any confusion with the old set.

### 1. `mecris_verify_code`: Authentication

Built from Meta's Authentication template library, with a copy-code button.

> *{{1}} is your verification code. For your security, do not share this code.*

- `{{1}}`: 6 digits.
- Sent only when the owner taps VERIFY in the app.
- At most 1 a minute and 5 a day (v0.3.0 already enforces this).

### 2. `mecris_optin_confirm`: Utility (opt-in confirmation)

> *You've turned on Mecris walk reminders for this number. I'll send at most
> {{1}} a day, between {{2}} and {{3}}. Reply LATER to snooze one, START when
> you head out, or STOP to turn them off.*

Example: *…at most 2 a day, between 2:00 PM and 6:00 PM. Reply LATER…*

- Sent once, right after the number is verified and walk reminders are
  switched on in the app.
- This is the only template that goes out without a prior reply, because it
  confirms an opt-in the owner just made.

### 3. `mecris_walk_reminder`: Utility (a reminder the owner turned on)

> *Your walk reminder: {{1}}. Reply START when you head out, or LATER and I'll
> ask again at {{2}}.*

Examples:
- *Your walk reminder: no walk logged yet today, and there's light until
  sunset at 4:41 PM. Reply START when you head out, or LATER and I'll ask again
  at 3:56 PM.*
- *Your walk reminder: 1,200 steps so far today, short of your 2,000. Reply
  START when you head out, or LATER and I'll ask again at 4:00 PM.*

- `{{1}}`: one factual clause built by the renderer from walk data and
  sunset. Weather is added only once a weather source is wired (#188); until
  then, Mecris must not claim any weather.
- `{{2}}`: the time LATER would pick (see below), so the message promises
  something concrete.

## Replies (what each word does)

Matched as whole words, case-insensitively, inside the 24-hour window that the
reply itself opens. Mecris answers each one in **freeform** text: no
template is needed inside the window.

- **LATER**: snooze. Mecris picks the time (rules below) and confirms it:
  *"OK, I'll check again at 3:56 PM. Sunset's at 4:41."*
- **START**: the owner is heading out. Mecris records the walk start (a manual
  start instead of opening Google Fit), stops today's reminders, and can
  confirm the result when the walk syncs: *"Nice, 34 minutes, 3,900 steps."*
- **STOP**: walk reminders off until the owner turns them back on in the app or
  replies **RESUME**. (START is taken for starting a walk.)
- Anything else gets one short freeform reply listing the three words. This
  epic does not parse free text.

## LATER: picking the snooze time

The goal is one more useful chance before dark, not a fixed delay:

1. **Latest useful time** = sunset − 45 minutes. Spin already computes sunset
   with v0.3.0's solar function.
2. If it's at least 45 minutes away, the snooze lands at the **earlier** of now
   + 2 hours or the latest useful time. A LATER at 2:00 PM in December (sunset
   about 4:40) gets a check at 3:55 PM; a LATER at 2:00 PM in June gets 4:00
   PM.
3. If no useful time is left today, Mecris says so and stops for the day:
   *"OK, it'll be dark by then. Tomorrow."*
4. A snooze is the owner's request, so the follow-up is a freeform message
   inside the open window. It doesn't count as a template, it is exempt from
   the 4-hour damping between *unrequested* reminders, and it still respects
   the daily window and night quiet.
5. One snooze per reminder. A second LATER means "not today."

## Send rules (the reply gate)

```
OFF ── owner verifies + enables walk reminders ──▶ ARMED (send optin_confirm)
ARMED ── reminder due, gates pass, < 2 templates today ──▶ send walk_reminder
LATER ──▶ snooze to the picked time (freeform, in-window)
START ──▶ walk recorded, reminders done for today
any reply ──▶ window open 24 h, "unanswered" count resets
2 delivered reminders in a row, unanswered ──▶ PAUSED until the owner writes or re-enables
STOP ──▶ OFF          RESUME ──▶ ARMED
account-level error (63051, 63112) ──▶ OFF everywhere, and the owner is alerted locally
```

"Unanswered" counts only reminders whose status reached `delivered`, so a send
that never arrived doesn't count against the owner.

## Rubric (every template and every rendered example)

- [ ] One purpose, stated in the fixed text, not in a variable.
- [ ] Says what happened and what to do next.
- [ ] Concrete values (times, steps); no "NOT FOUND", "EXPECTANT" or
      placeholder words; no claims the data can't back (e.g. weather before
      #188).
- [ ] Reads naturally aloud.
- [ ] Nothing promotional, persuasive or upselling; no emoji in
      authentication templates.
- [ ] A variable is neither the first nor the last word of the body
      (`mecris_verify_code` follows Meta's library format instead).
- [ ] Renders correctly with real data through the preview renderer (dry
      run, no send).

## Building it (code work, after this doc is approved)

1. `data/templates/*.json`: bodies, variables and categories kept in the
   repo, synced from the Twilio Content API (the script is in #378).
2. A preview renderer and rubric tests, using real walk and sunset data.
3. Store the message SID and delivery status, through a signed StatusCallback
   route in Spin.
4. Per-user reply-gate state, plus LATER/START/STOP/RESUME handling in the
   webhook: the snooze picker, and a manual walk start that the walk sync
   later reconciles.
5. One kill switch, `MECRIS_WHATSAPP_ENABLED`, checked by every send path:
   Spin, `send_reminder_message`'s template branch and `smart_send_message`.
6. Submit the three templates for approval and wait for the result.

## Later: conversational replies (separate epic)

The owner should eventually be able to say things that are more complex than
single words, for example "after lunch", "raining, skip today" or "walked
already, 40 min". That means understanding free text inside the window,
probably with an LLM within the budget rules. It also means deciding what
Mecris may do on its own. It is out of scope here, and the four reply words
above are designed to remain valid inside it.

## Re-enabling (owner decisions)

1. **Meta's review.** If the account is restored, continue below. If the ban
   is upheld, WhatsApp may simply be more trouble than it's worth; the owner
   may choose another platform rather than a new business portfolio. The
   reply words, snooze rules and rubric here are meant to carry over to
   whatever channel replaces it.
2. The templates are approved and the code above has shipped.
3. Only then:
   - recreate the `trigger-reminders` cron;
   - set `REMINDER_DELIVERY_METHOD=whatsapp`;
   - verify the number in the app, which sends `mecris_optin_confirm`.

Until then, the phone's local notifications remain the reminder channel.
