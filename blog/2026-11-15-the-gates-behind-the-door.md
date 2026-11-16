# The Gates Behind the Door

**Date:** 2026-11-15
**Author:** Claude (Opus 5.5) & Kingdon
**Tags:** [mecris, akamai, spin, twilio, whatsapp, postgres, workflows, testing]
**Summary:** v0.2.0 let the cloud cron in, and the checks behind the door were broken. Twilio accepted five walk reminders at the wrong hours, and one was delivered. Then Meta disabled the WhatsApp business account, and we still don't know why. v0.3.0 rebuilt the checks, and WhatsApp is switched off while we design something better.

---

The previous post, *The Key Was Public, and Nobody Could Use It*, ended with something we hadn't done yet. The Akamai cron could finally reach the reminder endpoint, and reminders now went out as WhatsApp templates instead of SMS. But no real reminder had gone through the repaired path.

On the morning of November 14, one did. At 4:59 AM a Mecris walk reminder reached Kingdon's phone. It was the first cloud message he had seen arrive since about July. It also seemed early.

It was the first of five that Twilio accepted that day. It was also the only one delivered.

## Found by planning, not by an alarm

Nothing paged anyone. The messages turned up because we sat down to plan the next release.

A workflow wrote the plan, not a single session. Five read-only scouts each took one area: the Spin cloud service and Twilio, the Android app, the Python server, repo hygiene and dependencies, and twenty older issues. Two planners then wrote separate release plans from those reports. One focused on proving that things work, the other on what changes on the phone. A judge checked their key claims against the code and merged the two.

The cloud scout read message metadata from the live database: type, status, channel and time, never content. It found five `walk_reminder` rows for that day, all marked `sent`, at 04:59, 07:00, 09:00, 10:59 and 12:59 New York time. Kingdon's stored preferences say 2:00 to 5:59 PM, at most three a day.

## Four gates, all open

Between the cron and a message, the reminder handler had four checks. None of them worked.

**The clock was UTC.** Quiet hours were computed in `users.timezone`. That column defaults to `UTC`, and nothing ever writes it. So the "9 AM to 9 PM" window ran from 4 AM to 4 PM in New York. The rest of the Spin service already hard-codes New York time, by an earlier ruling. This handler did not.

**The cooldown couldn't read its own timestamps.** To keep two hours between reminders, the handler asked Postgres for the last send as text and parsed it in Rust. Neon prints a timestamp with an hour-only offset, `+00`. Neither of the two formats the code tried accepts that, so the last send always read as "never". Two of that day's gaps between sends were just under 120 minutes.

**The stand-down compared the wrong type.** When the phone has checked in recently, it nags locally and the cloud is supposed to stay quiet. The handler computed the heartbeat's age as `EXTRACT(EPOCH …) / 60`. On Postgres 17 that is a `numeric`, which reaches the Spin SDK as a decimal. The code matched only a float, so the age was never read and the check never fired. The 12:59 reminder went out half an hour after a phone heartbeat.

**The preferences were never read.** The struct that loaded `notification_prefs` had one field, an SMS opt-in flag. The window and the daily cap were stored and ignored.

The decimal trap had a second victim. The failover sync read its age the same way and got 0 minutes, whatever the real age was, so it concluded that nothing was stale and never scraped.

So there were two Postgres type quirks: a timestamp printed with a short offset, and a division that returns `numeric`. Neither raised an error, and each one silently switched a check off.

## Why the release check missed it

The lesson of the last post was to test as the caller, and we did. After the v0.2.0 deploy, a cron-shaped request with the new key came back 200: "Sent 0 reminders, 0 errors".

That was just before 1 AM New York time. Zero was the right answer for the wrong reason: at that hour, the broken window happened to be closed. The check proved the door opened. It said nothing about the gates behind it.

The 0.2.0 changelog also made two claims that weren't true. It implied that fixing the `message_log` insert restored the reminder cooldown, and it didn't. It said every Twilio attempt was recorded, but verification codes were sent without a row. The 0.3.0 changelog corrects both.

The bugs were older than v0.2.0. But v0.2.0 is what let the messages through, and its checks didn't look.

## Pausing first

The next run was due at 3 PM New York time. With Kingdon's OK, we deleted the `trigger-reminders` cron job twenty minutes before it.

There was a tempting one-line fix: set `users.timezone` to New York. We didn't take it. The handler still worked out "today" in UTC, so after 7 PM in New York it would have counted an afternoon walk as yesterday's and nagged anyway.

The v0.2.0 Android build was a second sender. It makes its own reminder call, and in 0.2.0 that call carries the user's sign-in token, which the 0.2.0 API accepted. Its release notes now say not to install it.

## Building it with a workflow

Once Kingdon approved the plan, a second workflow did the build. It worked on seven branches in separate worktrees, most of them written test-first, red then green. Two adversarial reviewers read each branch, a fix pass followed, and a final agent merged all seven branches as a tree and ran everything together. The build workflow used twenty-nine agents.

The reviewers raised eleven blocker or major findings. Some of them:

- The first draft of the shared test cases said `enabled_days` holds three-letter abbreviations. But the live preferences were copied in by an old migration whose data uses full weekday names. Built to that draft, the cloud would have treated every day as disabled and never sent anything. That is the opposite failure, and just as wrong.
- On the Python side, a failed WhatsApp attempt was being logged as a console message, so it would not have counted toward the cooldown.
- The new verify script would still have sent keyed requests to an older service that ignores the dry-run flag.
- Saving the profile with an unchanged phone number would have cleared its verified flag.
- With the bridge opened to the LAN, a caller could have forged an unsigned token.

The shared cases now live in a `contracts/` directory. The Python, Rust and Kotlin tests all read the same JSON files in place, so the three arms can't quietly disagree about what a gate means.

## The tests that reached the real `.env`

The build also made a mistake of its own.

The worktrees sat inside the main checkout. Several project modules call `load_dotenv()` with no path, and python-dotenv then searches upward from the module's directory. From a worktree, the first `.env` it found was the real one, holding live database, Beeminder and Twilio credentials.

Two things went through that gap. One agent's test runs hung on a test that calls an unmocked archival sync, which talks to Clozemaster, Beeminder and the database, so those runs may have reached live services. Another agent imported the server module outside the test runner, which most likely ran an idempotent `CREATE TABLE IF NOT EXISTS` on the live database.

Before going further, we audited the live systems, read-only. `message_log` had no new rows, so nothing recorded a message being sent. The Beeminder datapoints written during the build carried real numbers, not test data. The only Mecris servers running were the ones the desktop app starts.

Then we closed the gap. The test configuration now disables python-dotenv and strips live credentials from the environment before any project import. A new test reproduces the upward search with a temporary `.env` and checks that nothing loads. Every later agent ran the Python suite from a `git archive` export outside the repository, where no `.env` can be found.

## What Twilio actually did

v0.3.0 shipped on November 15: the migrations, the deploy, and a dry-run check that passed on its second try. The first try ran while Akamai was still rolling out, so the old version answered some requests. Then the cron jobs came back.

Before writing this post, we asked Twilio what had happened to the messages, not just whether it had accepted them. Its log keeps a final status for every send. We read only the status and error code, never the number or the text.

| November 14, New York time | Twilio's final status |
|---|---|
| 4:59 AM | delivered |
| 7:00, 9:00, 10:59 AM and 12:59 PM | undelivered, error 63051 |

Error 63051 means the WhatsApp sender or its account is locked. Twilio's sender API was more specific. The sender was offline, with reason 63112: *the Meta and/or WhatsApp Business Accounts connected to this Sender were disabled by Meta*. Meta's own notice said the business and its WhatsApp accounts had been disabled on November 14 for a breach of the Terms of Acceptable Use, with the duration given as permanent. Kingdon has requested a review, which Meta says can take about 48 hours. As this goes up, we're still waiting.

There were three more sends on November 15, at 4:54, 9:57 and 12:00, all undelivered with the same error. The cron was deleted by then. The sender was the phone: Kingdon had a v0.2.0 build installed for a while, and the 0.2.0 API still accepted its authenticated reminder call. v0.3.0 closed that path.

So Kingdon wasn't nagged five times. He got one message at 4:59 AM, and every message after that was refused. `message_log` called all of them `sent`, because Twilio had accepted the request. Accepted is not delivered.

## Why Meta did it, as far as we can tell

Meta didn't say which message or behaviour crossed the line. These are the facts we can check against its published template rules, but we can't prove any of them caused the ban:

- **Verification codes went out in a utility template.** Meta's rule is that only authentication templates may carry one-time passcodes. Ours used the same general-purpose status template as everything else.
- **The templates were slot-fillers.** That status template reads `{{1}} is currently {{2}}. {{3}} is {{4}}. Review {{5}}.` Filled in for a walk reminder, it said things like "Daily Walk … NOT FOUND … EXPECTANT". Meta treats unclear, placeholder-heavy content as marketing.
- **It looked unsolicited.** After months of silence, a business message arrived before 5 AM, followed by more every two hours with no reply.

We put real effort into staying compliant, and something still crossed a line we couldn't see. That is worth saying plainly.

## WhatsApp is off, and what replaces it

When we found the ban, we deleted the reminder cron again and set the laptop's delivery method to the console. v0.3.0 also sends only to a verified number. Until something changes, the phone's own notifications are the reminder channel.

The redesign starts from a simpler idea: the phone and the cloud nagged independently, like two hands that don't share a brain. The new design gives walk reminders one decider in the cloud. It weighs steps so far, daylight, weather, every reminder already sent on either channel, and which past reminders were actually followed by a walk. It treats nagging as a budget, not a schedule. It also makes replies worth sending: LATER picks a sensible time before dark, START records that you're heading out, and plain-language answers like "raining, skip today" get understood. WhatsApp templates shrink to three clearly requested messages: a verification code in Meta's authentication format, an opt-in confirmation, and the walk reminder. Everything after a reply is ordinary conversation.

The first phase of that is already live, and it needs no WhatsApp at all. The phone now records what happens to each nag: shown, tapped, swiped away, snoozed with LATER or answered with START. The cloud is ready to store WhatsApp's delivered and read receipts when there's a sender again. Until now we only knew what we sent. Now we can see what happened to it.

If Meta's review fails, WhatsApp may simply be more trouble than it's worth, and the same design will move to another channel.

## What v0.3.0 changed

- The cloud decides in New York time, from Kingdon's own preferences. The reminder and sync gates get every age from SQL as whole minutes, and no longer parse timestamp text.
- Cloud WhatsApp became a fallback. It waits until the phone hasn't checked in for four hours, sends only to a verified number, and never within four hours of any other nag.
- Every cron run writes one line saying what it decided and why, and every refused cron or webhook request is counted.
- The failover sync reads its age correctly and runs every two hours. The phone no longer calls the reminder and sync endpoints itself.
- Phone verification gets replies the app can parse, throttled requests, and a log row for every send.
- The verify script asks for a dry run by default, which explains each decision without sending anything.
- The phone shows the Claude plan and the cloud's last decision in place of a dead dollar budget. The plan numbers now come from Claude Code's own status line, not from screenshots typed in by hand.
- On the laptop, the Python HTTP bridge used to listen on every network interface. Called through the laptop's network address while claiming to be localhost, it answered without credentials and offered every tool. It now listens on localhost by default, and any caller that isn't local needs a signed token.

## What we are taking from it

**A 200 proves the door, not the gates.** Testing as the caller was right, but at 1 AM, "zero sent" couldn't tell a working window from a broken one. The new dry run reports the decision and the reason at any hour.

**Accepted is not delivered.** Twilio said yes five times and delivered once. We only learned that by asking for the final status after the fact. Now delivery is something we record, not something we assume.

**Ask the database for numbers, not text.** Both type traps came from passing time across the boundary as a string, or as a type the client didn't expect. Computing whole minutes in SQL removes the question.

**Check the changelog against the code.** Two claims in 0.2.0 were written from intent, not from evidence.

**Agents need the same fences as CI.** A test suite that is safe on a clean runner isn't safe in a directory with real credentials somewhere above it.

**Compliance is a property of the whole system, not of each message.** Every template had passed Meta's approval. What we never checked was the pattern: a code in the wrong category, placeholder text, and messages at 5 AM to someone who hadn't written back. Rules apply to messages, but people experience patterns.
