---
name: mecris-plan
description: 'Write a minimal spec as a GitHub issue before acting. Takes the recommended action from mecris-orient and records intent, rationale, and validation criteria. This is the red in red-green-archive. Trigger with /mecris-plan'
---

# mecris-plan

Spec-writing skill for the Mecris accountability system. Before any code is touched or action is taken, write a three-line GitHub issue on yebyen/mecris recording what will be done, why, and how to know it worked. Consumes the orient report. Produces an auditable spec.

## When to Activate
- After `/mecris-orient` has produced a situation report with a recommended action
- Before writing any code, making any commit, or triggering any workflow
- When the user says "plan", "write the spec", "what's the plan", "/mecris-plan"

## Slash Command

### `/mecris-plan`

Runs the full planning workflow:

1. Take the recommended action from the current orient report (must have run `/mecris-orient` first)
2. Draft a three-part spec:
   - **Intent**: one sentence — what will be done
   - **Because**: one sentence — what in the orient report motivates this
   - **Validation**: one sentence — how to confirm it worked
3. Open a GitHub issue on yebyen/mecris with title `[plan] {intent}` and body containing all three parts
4. **RECORD** the issue number in your internal scratchpad/history immediately — you will need it for `/mecris-archive`.
5. **VERIFY** that the issue creation was successful before proceeding to work.

**Usage**: Type `/mecris-plan` after orienting. The spec issue will be opened before any action proceeds.

## Spec Format

Issue title: `[plan] {one-line description of action}`

Issue body:
```
**Intent**: {what will be done — specific and concrete}

**Because**: {what orient showed that motivates this — cite the source: issue number, commit, or NEXT_SESSION.md item}

**Validation**: {observable outcome that confirms success — test pass, issue closed, datapoint in Beeminder, etc.}
```

## Examples

### Sync from upstream
```
[plan] Sync yebyen/mecris from kingdonb/mecris main (18 commits behind)

**Intent**: Fetch and merge kingdonb/mecris main into yebyen/mecris.

**Because**: Orient showed yebyen/mecris is 18 commits behind upstream with no merge conflicts anticipated.

**Validation**: `git rev-list --count HEAD..upstream/main` returns 0.
```

### Fix a bug
```
[plan] Fix multiplier lever SQL query to respect user_id column

**Intent**: Update the SQL in the Rust service to use the composite primary key (user_id, language_name).

**Because**: NEXT_SESSION.md lists multiplier sync as unverified; issue #122 reports persistence race condition.

**Validation**: `SELECT pump_multiplier FROM language_stats WHERE user_id = ?` returns the value set in the Android app.
```

### Trigger pr-test
```
[plan] Run pr-test for kingdonb/mecris#142

**Intent**: Dispatch the pr-test workflow against PR #142 and post results as a comment.

**Because**: Orient found issue tagged needs-test referencing PR #142.

**Validation**: Comment posted on kingdonb/mecris#142 with ✅ or ❌ for both Python and Android tests.
```

## Notes

- This skill opens exactly one issue per invocation — no more
- The issue stays open until `/mecris-archive` closes it
- If orient did not run first, run `/mecris-orient` before proceeding
- In bot context: the plan issue is the only thing an outside observer can see before the work starts — make it legible to a human
- Keep specs small: if the intent requires more than one sentence, the action is too large — split it
