# Implementation Tasks

## Phase 1: Credential Setup

- [ ] Create fine-grained PAT in GitHub with scope limited to `kingdonb/mecris` only
  - Permissions: `contents: read/write`, `metadata: read`
  - No other permissions
- [ ] Add PAT as `MECRIS_AUTONOMOUS_PAT` secret in `kingdonb/mecris` repository settings
- [ ] Document PAT expiration date and set calendar reminder for rotation

## Phase 2: Workflow Configuration

- [ ] Create `mecris-autonomous.yml` workflow (or modify existing `mecris-bot.yml`)
- [ ] Configure git identity as `mecris-autonomous-bot` with noreply email
- [ ] Use `MECRIS_AUTONOMOUS_PAT` for checkout and push
- [ ] Verify workflow cannot access other repositories (test with intentional failure)

## Phase 3: Verification

- [ ] Trigger test run of autonomous workflow
- [ ] Confirm commits appear as `mecris-autonomous-bot`, not personal user
- [ ] Confirm PAT cannot push to any other repository
- [ ] Review GitHub Actions logs for any credential leakage

## Phase 4: Cleanup (Optional)

- [ ] Revoke any broader PATs that are no longer needed
- [ ] Update `docs/AGENT_AGENDA_DESIGN.md` with reference to this isolated identity pattern
- [ ] Add entry to `session_log.md` documenting the identity isolation setup
