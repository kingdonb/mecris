# Walk reminders: one brain, two channels (draft for #363)

**Status:** draft. The owner's second review is folded in (2026-11-15).
Nothing here is submitted to Meta, and no code sends with it yet. WhatsApp
stays switched off until Meta's review is decided and this design is approved
and built (see "Re-enabling" below). Most of the design is useful even if
WhatsApp never comes back.

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
   placeholder-only content as marketing.
3. **The sending pattern looked unsolicited.** After months of silence, a
   business-initiated message arrived at 04:59, then more every two hours with
   no reply.

A deeper problem sits under all three. **The phone and the cloud nagged
independently**, like two hands that don't share a brain: neither knew what
the other had sent, whether it arrived, or whether it helped.

## Scope

**Walking.** The Android app's language nags (Arabic, Greek) work well and
stay as they are. Everything about getting the owner out for a walk moves to
one decision-maker, whichever channel delivers the reminder.

## One brain: the walk decider

A single decider owns every walk reminder, on every channel. It runs in the
cloud (Spin, on the cron), because only the cloud sees all the inputs. The
phone stops deciding walk nags on its own. It shows what the decider asks it
to show, and it reports back what happened.

**Each time, it decides:** whether to remind now, on which channel (phone
notification or WhatsApp), with what words, and when to look again.

**Inputs:**

| Input | Source |
|---|---|
| Steps and walks so far today | `walk_inferences` (Health Connect via the phone) |
| Daylight: sunrise, sunset, dark | v0.3.0's solar function in Spin |
| Weather now and in the next hours | to be wired (#188), part of this work |
| Every reminder sent today on any channel, and what happened to it | `message_log` plus delivery and interaction events (below) |
| What has worked before: which reminders, at which times and on which days, were followed by a walk | history in `message_log` + `walk_inferences` (#350) |
| Whether the owner is busy or away | the phone's activity, vacation mode, a recent "skip" |
| The owner's stated preferences | notification prefs: a preferred window as a hint, not a fence; max per day; days |

**Nagging is a budget, not a rule:**
- About **2 unrequested reminders a day**, across both channels together.
- A reminder the owner **asked for** (a LATER snooze) is not unrequested. It
  may be a third message, and it doesn't count against the budget.
- **Back off when ignored.** If two reminders in a row are delivered or shown
  but get no reaction, stop for the day. If that keeps happening across days,
  send fewer and at the times that have worked.
- Never at night. Never while the owner is clearly mid-walk or just finished
  one.
- No fixed window. The decider picks times from daylight, weather and history.
  The preferred window in the prefs is a starting hint.

## What each channel can tell us

This answers the owner's question: can we see whether reminders were
delivered and observed?

| Signal | Phone notification | WhatsApp |
|---|---|---|
| Sent or posted | yes; logged today as `shown` | yes (Twilio accepted it) |
| Delivered | yes; posted means on the device | yes, from the status callback |
| Seen | **not without interaction.** Android doesn't report a glance. | **yes, as `read`**, if the owner's read receipts are on |
| Tapped or opened | possible; the tap opens the dashboard but **isn't logged yet** | n/a (a reply is the interaction) |
| Dismissed (swiped away) | possible with a delete intent; **not wired yet** | n/a |
| Action button pressed (LATER, START) | possible; **not wired yet** (today's buttons only open the app) | the reply word |
| Blocked or muted | yes: notifications off, or the channel set to silent | the sender's status, plus errors such as 63051 |

So "observed" means **read** on WhatsApp, and **tapped, dismissed or acted on**
on the phone. A notification that is shown and then ignored looks the same as
one never seen. The decider treats "no reaction" as no reaction, whatever the
reason.

## Conversation: the core of this feature

Reminders only work if answering them does something. The owner should be able
to talk to Mecris in plain language. This is not a general chatbot: every
message maps to a small set of things Mecris can actually do.

**The same words work everywhere.** The phone notification gets action buttons
(LATER, START), and WhatsApp accepts the same words as replies, so the two
channels behave the same.

**Single words, handled without an LLM:**
- **LATER**: snooze. Mecris picks the time and says it.
- **START**: heading out now. This records a walk start, so there's no need to
  open Google Fit. It ends today's reminders, and Mecris confirms the result
  when the walk syncs.
- **STOP** / **RESUME**: walk reminders off or back on.

**Free text** is understood with an LLM inside the conversation window, and
turned into one of these intents:

| The owner says | Intent | Mecris does |
|---|---|---|
| "after lunch", "in an hour", "at 3" | snooze until | sets the time and confirms it ("OK, 1:30. Sunset's at 4:41.") |
| "raining, skip today", "not today" | skip, with a reason | no more walk reminders today; the reason is kept so the decider learns |
| "walked already, 40 min" | report a walk | logs it, or matches it to the synced walk, and stops reminding |
| "how am I doing?", "steps today?" | ask | answers from real data |
| "only weekends", "not before noon" | change a preference | proposes the change and applies it after a yes |
| anything else | unclear | one short reply that says what Mecris can do |

**Guardrails:**
- The LLM only classifies and fills in values. A fixed list of actions does
  the work.
- Anything that changes data or preferences is confirmed first.
- Replies are short and factual, in Mecris's own voice ("I" is fine).
- Message text is handled under the PII rules: encrypted at rest, never
  logged in plain text.
- The LLM call runs through the budget governor.

## LATER: picking the snooze time

The goal is one more useful chance, not a fixed delay:

1. The decider proposes the best next time using daylight, the forecast and
   history. For example, the next dry stretch before dark, or the time the
   owner usually walks.
2. In winter it aims to land before dark. A LATER at 2:00 PM in December
   (sunset about 4:40) comes back around 3:55, not after a fixed 4 hours.
3. If no useful time is left today, Mecris says so and stops: *"It'll be dark
   by then. Tomorrow."*
4. The follow-up was requested, so it can be a third message. On WhatsApp it
   goes out as a freeform reply inside the window that the LATER opened.
5. A second LATER for the same reminder counts as a skip for the day, unless
   the owner gave a time.

## WhatsApp templates

Templates are only needed for messages Mecris starts. Everything after a
reply is freeform text. All 14 existing templates are retired.

1. **`mecris_verify_code`** (Authentication, from Meta's library, with a
   copy-code button): *{{1}} is your verification code. For your security, do
   not share this code.* Sent only when the owner taps VERIFY.
2. **`mecris_optin_confirm`** (Utility, opt-in confirmation): *You've turned on
   Mecris walk reminders for this number. I'll keep them to a couple a day and
   only when there's light to walk in. Reply LATER to snooze one, START when
   you head out, or STOP to turn them off.*
3. **`mecris_walk_reminder`** (Utility, a reminder the owner turned on): *Your
   walk reminder: {{1}}. Reply START when you head out, or LATER and I'll find
   a better time.* `{{1}}` is one factual clause from the decider, for
   example *"no walk logged yet today; it's 48°F and dry until about 4, and
   sunset is at 4:41"*. It names weather only from a real forecast.

## Rubric (every template and every rendered message)

- [ ] One purpose, in the fixed text.
- [ ] Says what happened and what to do next.
- [ ] Concrete values; no placeholder words; no claim the data can't back.
- [ ] Reads naturally aloud.
- [ ] Nothing promotional or persuasive; no emoji in authentication
      templates.
- [ ] A variable is neither the first nor the last word (the authentication
      template follows Meta's format instead).
- [ ] Renders correctly with real data through the preview renderer.

## Building it, in phases

Each phase is useful on its own, and phases 1–3 need no WhatsApp at all.

1. **See what happens.**
   - The phone logs `tapped`, `dismissed`, `action:LATER` and `action:START`
     for its notifications, and reports whether notifications are enabled.
   - WhatsApp stores the message SID and the delivery and read status, via a
     signed StatusCallback route in Spin.
2. **One brain.**
   - The decider in Spin owns walk reminders.
   - The phone's walk nag asks it and reports back, instead of deciding on
     its own.
   - The notification actions (LATER, START) go to the decider.
3. **Know the sky.** Weather is wired (#188) and goes into decisions and
   messages.
4. **Talk.**
   - Single words, then free-text intents through the LLM, on both channels.
   - Confirmations and the guardrails above.
5. **WhatsApp again**, only if Meta allows it:
   - the three templates are submitted and approved;
   - one kill switch, `MECRIS_WHATSAPP_ENABLED`, covers every send path
     (Spin, `send_reminder_message`'s template branch and
     `smart_send_message`);
   - sends stop on an account-level error (63051, 63112).

## Re-enabling WhatsApp (owner decisions)

1. **Meta's review.** If the account is restored, continue below. If the ban
   is upheld, WhatsApp may be more trouble than it's worth, and another
   platform may replace it. Phases 1–4 carry over to any channel.
2. Phase 5 is built and the templates are approved.
3. Then:
   - recreate the `trigger-reminders` cron;
   - set `REMINDER_DELIVERY_METHOD=whatsapp`;
   - verify the number in the app, which sends `mecris_optin_confirm`.
