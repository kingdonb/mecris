# CI/CD Workflows for Pi + Mecris Bridge

> GitHub Actions automation for validating the Pi extension bridge to Mecris.

## Workflows

### `e2e-pi-mecris.yml`

**Validates the Pi + Mecris bridge at every commit and PR.**

**Triggers:**
- Push to `main` (if bridge-related files changed)
- Pull request to `main` (if bridge-related files changed)
- Manual dispatch (`workflow_dispatch`) with optional model/provider override

**What it does:**

1. **Setup**
   - Installs Node.js 20 (for Pi CLI and extension)
   - Installs Python + uv (for MCP server)
   - Spins up a local PostgreSQL 16 (test database)
   - Installs npm deps for the extension

2. **Validation**
   - ✅ MCP server startup: Verifies `mcp_stdio_server.py` responds
   - ✅ Extension schema: Checks for key patterns (TypeBox, tool registration, lazy-load)
   - ✅ Test script: Confirms E2E test cases are defined and executable
   - ✅ Python unit tests: Runs `pytest tests/` if present

3. **Reporting**
   - Posts a summary to the GitHub Actions log
   - Uploads test logs as artifacts
   - Records validation status (MCP ✅, schema ✅, tests ✅, etc.)

**Status badge:** (Add to `README.md` if desired)
```markdown
[![E2E Bridge Tests](https://github.com/kingdonb/mecris/actions/workflows/e2e-pi-mecris.yml/badge.svg?branch=main)](https://github.com/kingdonb/mecris/actions/workflows/e2e-pi-mecris.yml)
```

**Example run:** https://github.com/kingdonb/mecris/actions/workflows/e2e-pi-mecris.yml

---

## Full E2E Testing (With Live Provider Credentials)

The current workflow validates **setup and structure** without requiring live provider
credentials (GitHub Copilot, Groq, Anthropic). To run the **full end-to-end tests**
that actually call models:

### Option 1: Local Testing (Recommended for Development)

Run directly on your machine:

```bash
# Set up once
npm install -C .pi/extensions/mecris
uv venv && uv pip install -r requirements.txt

# Run tests
./tests/e2e_pi_mecris.sh
```

The script uses your default Pi provider (from `~/.pi/agent/settings.json`).

### Option 2: GitHub Actions with Secrets (Future Enhancement)

To add live E2E tests to CI, we'd need to:

1. **Store credentials as GitHub Secrets:**
   - `GITHUB_COPILOT_TOKEN` (or configure in org settings)
   - `GROQ_API_KEY` (optional)
   - `ANTHROPIC_API_KEY` (optional)

2. **Update workflow:**
   ```yaml
   - name: Configure provider credentials
     env:
       GITHUB_COPILOT_TOKEN: ${{ secrets.GITHUB_COPILOT_TOKEN }}
       GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
     run: |
       mkdir -p ~/.pi/agent
       # Write auth.json for the provider
       ...
   
   - name: Run full E2E tests
     run: ./tests/e2e_pi_mecris.sh
   ```

   **Security consideration:** Credentials should be organization-level secrets, not
   repo-level, to minimize blast radius if the repo is compromised.

3. **Branch protection:** Require E2E tests to pass before merging PRs.

---

## Current Test Artifacts

When the workflow runs, it uploads:

- **`test-logs/mcp-startup.log`** — MCP server initialization output
- **`test-logs/pytest-output.txt`** — Python unit test results

These are available as artifacts on the Actions run page for 7 days.

---

## Workflow File: `e2e-pi-mecris.yml`

Key sections:

### Triggers (Lines 3–35)

```yaml
on:
  push:
    branches: [main]
    paths:  # Only run if these files changed
      - .pi/extensions/mecris/**
      - tests/e2e_pi_mecris.*
      - mcp_*.py
      - .github/workflows/e2e-pi-mecris.yml
  pull_request:
    branches: [main]
    paths: [...]
  workflow_dispatch:  # Manual run with optional overrides
    inputs:
      model: ...
      provider: ...
```

### Services (Lines 37–49)

```yaml
services:
  postgres:
    image: postgres:16
    ports: [5432:5432]
    # MCP server can connect to this for test data
```

### Steps

| Step | Purpose |
|---|---|
| Checkout | Clone the repo |
| Set up Node.js | Install Node 20 for Pi CLI + extension |
| Install Pi CLI | `npm install -g @earendil-works/pi-coding-agent` |
| Install extension deps | `npm install` in `.pi/extensions/mecris/` |
| Set up Python | Install uv and Python 3.12+ |
| Install Python deps | `uv pip install -r requirements.txt` |
| Init test database | Run schema migrations on local postgres |
| **Test MCP server** | Spawn `mcp_stdio_server.py` and verify startup |
| **Validate schema** | Check extension TypeScript for expected patterns |
| **Dry-run E2E** | Verify test script is executable and has test cases |
| Run Python tests | `pytest tests/` (if any unit tests exist) |
| Upload artifacts | Save logs for inspection |
| Report results | Post summary to GitHub Actions log |

---

## Extending the Workflow

### Add a live E2E step (requires secrets)

```yaml
- name: Run live E2E tests
  if: env.GITHUB_COPILOT_TOKEN != ''
  env:
    GITHUB_COPILOT_TOKEN: ${{ secrets.GITHUB_COPILOT_TOKEN }}
  run: |
    ./tests/e2e_pi_mecris.sh
```

### Run against multiple providers

```yaml
strategy:
  matrix:
    provider:
      - github-copilot
      - groq
  fail-fast: false

- name: E2E with ${{ matrix.provider }}
  run: ./tests/e2e_pi_mecris.sh ${{ matrix.provider }}
```

### Post PR comment with results

```yaml
- name: Post PR comment
  if: github.event_name == 'pull_request'
  uses: actions/github-script@v7
  with:
    script: |
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: '✅ E2E bridge tests passed'
      })
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Workflow doesn't trigger | Check `paths` — did the right files change? |
| MCP startup fails | Check Python venv, check `mcp_stdio_server.py` syntax |
| Database init fails | Postgres service may not be ready; check logs |
| Artifacts not uploaded | Upload step may have failed; check for errors in logs |
| Python tests fail | Not all Python tests are required to pass; review failures |

---

## Maintenance

### Scheduled cleanup

Add a scheduled job to periodically clean up old artifacts (optional):

```yaml
name: cleanup-old-artifacts
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  clean:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/github-script@v7
        with:
          script: |
            const artifacts = await github.rest.actions.listArtifactsForRepo({
              owner: context.repo.owner,
              repo: context.repo.repo
            });
            for (const a of artifacts.data.artifacts) {
              if (new Date(a.created_at) < new Date(Date.now() - 30*24*60*60*1000)) {
                await github.rest.actions.deleteArtifact({...});
              }
            }
```

---

## See Also

- `.github/workflows/ci.yml` — Main CI for Python/Rust/Android tests
- `.github/workflows/pr-test.yml` — PR test harness with full test suite
- `tests/e2e_pi_mecris.md` — E2E test specification
- `tests/e2e_pi_mecris.sh` — E2E test runner (bash)

