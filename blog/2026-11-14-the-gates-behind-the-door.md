# The Gates Behind the Door

**Date:** 2026-11-14
**Author:** Claude (Opus 5.5) & Kingdon
**Tags:** [mecris, akamai, spin, twilio, postgres, workflows, testing]
**Status:** draft
**Summary:** v0.2.0 let the cloud cron in. The checks behind the door were broken, and five walk reminders went out at the wrong hours. We found it while planning, paused the cron, and v0.3.0 rebuilds the checks.

---

The previous post, *The Key Was Public, and Nobody Could Use It*, ended with something we hadn't done yet. The Akamai cron could finally reach the reminder endpoint, and reminders now went out as WhatsApp templates instead of SMS. But no real reminder had gone out through the repaired path yet.

On the morning of November 14, one did. A Mecris walk reminder reached Kingdon's phone. It was the first cloud message he had seen arrive since about July. It also seemed early.

It was one of five.

## Found by planning, not by an alarm

Nothing paged anyone. The messages turned up because we sat down to plan the next release.

A workflow wrote the plan, not a single session. Five read-only scouts each took one area: the Spin cloud service and Twilio, the Android app, the Python server, repo hygiene and dependencies, and twenty older issues. Two planners then wrote separate release plans from those reports. One focused on proving that things work, the other on what changes on the phone. A judge checked their key claims against the code and merged the two.

The cloud scout read message metadata from the live database: type, status, channel and time, never content. It found five `walk_reminder` rows for that day, all accepted by Twilio, at 04:59, 07:00, 09:00, 10:59 and 12:59 New York time. Kingdon's preferences allow reminders from 2:00 to 5:59 PM, at most three a day.

## Four gates, all open

Between the cron and a message, the reminder handler had four checks. None of them worked.

**The clock was UTC.** Quiet hours were computed in `users.timezone`. That column defaults to `UTC`, and nothing ever writes it. So the "9 AM to 9 PM" window ran from 4 AM to 4 PM in New York. The rest of the Spin service already hard-codes New York time, by an earlier ruling. This handler did not.

**The cooldown couldn't read its own timestamps.** To keep two hours between reminders, the handler asked Postgres for the last send as text and parsed it in Rust. Neon prints a timestamp with an hour-only offset, `+00`. Neither of the two formats the code tried accepts that, so the last send always read as "never". Two of that day's gaps between sends were just under 120 minutes.

**The stand-down compared the wrong type.** When the phone has checked in recently, it nags locally and the cloud is supposed to stay quiet. The handler computed the heartbeat's age as `EXTRACT(EPOCH …) / 60`. On Postgres 17 that is a `numeric`, which reaches the Spin SDK as a decimal. The code matched only a float, so the age was never read and the check never fired. The 12:59 reminder went out half an hour after a phone heartbeat.

**The preferences were never read.** The struct that loaded `notification_prefs` had one field, an SMS opt-in flag. The window and the daily cap were stored and ignored.

The decimal trap had a second victim. The failover sync read its age the same way and got 0 minutes, whatever the real age was, so it concluded that nothing was stale. Its first run under the new key was set to answer "Failover sync: 0 success" and scrape nothing.

So there were two Postgres type quirks: a timestamp printed with a short offset, and a division that returns `numeric`. Neither raised an error, and each one silently switched a check off.

## Why the release check missed it

The lesson of the last post was to test as the caller, and we did. After the v0.2.0 deploy, a cron-shaped request with the new key came back 200: "Sent 0 reminders, 0 errors".

That was just before 1 AM New York time. Zero was the right answer for the wrong reason: at that hour, the broken window happened to be closed. The check proved the door opened. It said nothing about the gates behind it.

The 0.2.0 changelog also made two claims that weren't true. It implied that fixing the `message_log` insert restored the reminder cooldown, and it didn't. It said every Twilio attempt was recorded, but verification codes were sent without a row. Both corrections belong in the 0.3.0 changelog.

The bugs were older than v0.2.0. But v0.2.0 is what let the messages through, and its checks didn't look.

## Pausing first

The next run was due at 20:00 UTC, 3 PM in New York. With Kingdon's OK, we deleted the `trigger-reminders` cron job at 19:40 UTC, twenty minutes before that run, so there was no sixth message. The failover jobs stayed, since they were doing nothing anyway.

There was a tempting one-line fix: set `users.timezone` to New York. We didn't take it. The handler still worked out "today" in UTC, so after 7 PM in New York it would have counted an afternoon walk as yesterday's and nagged anyway.

Two more stop-gaps went out as advice. The v0.2.0 Android build makes its own reminder call, and in 0.2.0 that call authenticates, so installing it would have added sends through the same broken gates. Its release notes now say not to install it. The app's verify button also had to wait. The cloud answered it with a bare JSON string the app couldn't parse, so the code would have arrived with no dialog to enter it in.

## Building it with a workflow

Once Kingdon approved the plan, a second workflow did the build. It worked on seven branches in separate worktrees, most of them written test-first, red then green. Two adversarial reviewers read each branch, a fix pass followed, and a final agent merged all seven branches as a tree and ran everything together. The build workflow used twenty-nine agents.

The reviewers raised eleven blocker or major findings. Some of them:

- The first draft of the shared test cases said `enabled_days` holds three-letter abbreviations. But the live preferences were copied in by an old migration whose data uses full weekday names. Built to that draft, the cloud would have treated every day as disabled and never sent anything. That is the opposite failure, and just as wrong.
- On the Python side, a failed WhatsApp attempt was being logged as a console message, so it would not have counted toward the cooldown.
- The new verify script would still have sent keyed requests to an older service that ignores the dry-run flag.
- Saving the profile with an unchanged phone number would have cleared its verified flag.
- With the bridge opened to the LAN, a caller could have forged an unsigned token.

The shared cases now live in a `contracts/` directory. The Python, Rust and Kotlin tests all read the same JSON files in place, so the three arms can't quietly disagree about what a gate means. In the build's final check, every pair of branches merged cleanly, and the combined tree passed 2,075 Python tests, 115 Rust tests and 150 Android tests.

## The tests that reached the real `.env`

The build also made a mistake of its own.

The worktrees sat inside the main checkout. Several project modules call `load_dotenv()` with no path, and python-dotenv then searches upward from the module's directory. From a worktree, the first `.env` it found was the real one, holding live database, Beeminder and Twilio credentials.

Two things went through that gap. First, one agent's full test runs hung for about 17 and 5 minutes on a test that calls an unmocked archival sync, which talks to Clozemaster, Beeminder and the database, so those runs may have reached live services. Second, at least one agent imported the server module outside the test runner to check a path. Its log showed a usage tracker initializing its tables, most likely on the live database, which would mean an idempotent `CREATE TABLE IF NOT EXISTS` ran there.

Before going further, we audited the live systems, read-only:

- **The database:** every timestamp column, for rows written since the build started. `message_log` had no new rows, so nothing recorded a message being sent. The other rows looked like the day's ordinary traffic: heartbeats, balance checks, review-count syncs and one Claude usage reading.
- **Beeminder:** five goals, covering the walk goal, the two language goals, the review stack and Claude usage. Only the review stack and the Claude goal had new datapoints, and they carried real numbers, not test data. From the data alone, we couldn't tie every one of them to a caller.
- **The process list:** the only Mecris servers running were the three MCP servers the desktop app starts.

Then we closed the gap three ways. The test configuration now disables python-dotenv and strips live credentials from the environment before any project import. Only a database URL on localhost survives, for CI's Postgres. A new test reproduces the upward search with a temporary `.env` and checks that nothing loads. And every later agent was told to run the Python suite from a `git archive` export outside the repository, where no `.env` can be found, and never to import project modules outside pytest. CI, for its part, now generates its Spin keys fresh for each run.

## What v0.3.0 changes

- The cloud decides in New York time, from Kingdon's own preferences. The reminder and sync gates get every age from SQL as whole minutes, and no longer parse timestamp text.
- Cloud WhatsApp is a fallback. It waits until the phone hasn't checked in for four hours and sends only to a verified number. It never sends within four hours of any other nag, including ones the phone showed, and sends at most three a day.
- Every cron run writes one line saying what it decided and why, and every refused cron or webhook request is counted. Silence now means the cron stopped, not that it ran and did nothing.
- The failover sync reads its age correctly and runs every two hours, scraping when the data is 100 minutes old or more. The phone no longer calls the reminder and sync endpoints itself.
- The cloud answers phone verification with replies the app can parse, throttles repeated requests, and logs every verification send.
- The verify script no longer sends a reminder by default. It asks the reminder endpoint for a dry run, which explains each decision without sending anything, and it makes no request with the real key until `/version` says the service supports the dry run.
- The phone shows the Claude plan and the cloud's last decision in place of a dead dollar budget.
- The Claude plan numbers no longer come from screenshots typed in by hand: Claude Code passes its own plan usage to a status line command, which saves it where Mecris can read it. It only updates while Claude Code is in use, and the per-model weekly limit still has to be entered by hand.
- On the laptop, the Python HTTP bridge used to listen on every network interface. When we called it through the laptop's network address while claiming to be localhost, it answered without credentials and offered every tool. It now listens on localhost by default, its open `/mcp` endpoint is gone, and any caller that isn't local needs a signed Pocket ID token.

A quieter cloud is the expected result. With the phone checking in every hour, the cloud should rarely send anything, and the dry run and the cron's status line will say why.

## Not proven yet

v0.3.0 is not deployed yet. Still to do: the database migrations, the deploy and a dry-run check, recreating the cron jobs, then three clean cron cycles. After that come the new app on the phone, a verified number, a reply test, and three days of `message_log` with no reminder outside the window.

One gap stays open. Twilio accepted all five of those messages, and Kingdon noticed one. Spin doesn't record Twilio's message ID or delivery status, so we can't say which of the others arrived. Recording delivery is not in this release.

## What we are taking from it

**A 200 proves the door, not the gates.** Testing as the caller was right, but at 1 AM, "zero sent" couldn't tell a working window from a broken one. The new dry run reports the decision and the reason at any hour.

**Ask the database for numbers, not text.** Both traps came from passing time across the boundary as a string, or as a type the client didn't expect. Computing whole minutes in SQL removes the question.

**Check the changelog against the code.** Two claims in 0.2.0 were written from intent, not from evidence.

**Agents need the same fences as CI.** A test suite that is safe on a clean runner isn't safe in a directory with real credentials somewhere above it.
