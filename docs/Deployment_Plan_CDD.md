# Deployment Plan CDD

**Context**
- Mecris consists of several functional *arms*:
  - **MCP server** – provides JSON endpoints (`/narrator/context`, `/beeminder/status`, `/usage`).
  - **Budget arm** – stores Claude and Groq billing data in `mecris_usage.db`.
  - **Beeminder arm** – monitors goals, detects derail risk, and records alerts.
  - **Heuristic/cron arm** – runs periodically, evaluates Beeminder & budget risk, decides whether to notify via **Twilio**.
  - **Twilio A2P compliance arm** – sends SMS/voice alerts to the user when the heuristic decides a notification is needed.
  - **LLM proxy** – `claude-code-proxy` + `LiteLLM` allow switching between Anthropic, Groq, and other back‑ends.
  - **Deployment options** – AWS t4g.small (5 h/day), Lambda functions, or Kubernetes clusters.  `aws-accounts` repo contains user‑data scripts for EC2 ASGs.

**Decision**
Implement a production‑ready, autonomous workflow that:
1. **Runs the MCP server** on a lightweight compute target (EC2 or Lambda) with automatic restart on failure.
2. **Executes the heuristic** as a cron job (or CloudWatch Events) that:
   - Pulls `/beeminder/status` and `/usage`.
   - Flags any goal with `derail_risk == "WARNING"` or budget health != "GOOD".
   - Enforces a *once‑per‑day* notification limit per goal to avoid spamming.
3. **Triggers Twilio** only when a new high‑severity condition appears (first warning of the day, budget breach, or missing daily walk).  The Twilio arm respects A2P compliance by using a pre‑registered messaging service.
4. **Caches budget data** in `mecris_usage.db` with two rows (Anthropic, Groq).  Cache TTL = 15 min; refresh on each heuristic run.
5. **Deploys** via Infrastructure‑as‑Code (IaC):
   - **Option A – EC2**: Use `aws-accounts` user‑data to install `uv`, the MCP server, and the cron script.  Attach an IAM role with SSM access for remote debugging.
   - **Option B – Lambda**: Package the MCP server and heuristic as separate Lambda functions; use EventBridge to schedule the heuristic.
   - **Option C – EKS**: Deploy as Docker containers behind a Service; use K8s `CronJob` for the heuristic.
   - Choose the cheapest option that satisfies the 5 h/day compute ceiling; default to **Option A** (t4g.small) with auto‑scaling to 0 instances outside the window.

**Implementation Steps**
1. **Create IaC templates** (`infra/ec2.tf`, `infra/lambda.tf`, `infra/eks.yaml`).  Include user‑data that runs `uv sync && uv run scripts/launch_server.sh`.
2. **Add heuristic script** (`scripts/heuristic.sh`) that:
   - Calls `curl http://localhost:8000/beeminder/status` and `.../usage`.
   - Evaluates risk and writes a JSON flag to `/tmp/heuristic_state.json`.
   - Invokes Twilio via `twilio-cli` only if `state.changed == true`.
3. **Integrate Twilio**:
   - Store `TWILIO_SID`, `TWILIO_TOKEN`, and `FROM_NUMBER` in AWS Secrets Manager.
   - Provide a small wrapper (`scripts/send_alert.py`) that reads the secret and sends the SMS.
4. **Update budget arm**:
   - Add `groq_usage` column to `mecris_usage.db`.
   - Implement `scripts/update_groq_budget.py` (use Groq billing endpoint, cache 15 min).
5. **Modify MCP server config** (`config.yaml` if present) to read both budget sources and expose them via `/usage`.
6. **Testing**:
   - Unit tests for heuristic decision logic (`tests/test_heuristic.py`).
   - Integration test that simulates a warning goal and checks Twilio call is made (mock Twilio API).
7. **CI/CD**:
   - GitHub Actions workflow that lints, runs tests, and applies IaC with `terraform plan/apply` on a staging AWS account.
8. **Documentation**:
   - Add a CDD entry (`docs/Heuristic_Notification_CDD.md`) describing the notification throttling policy.
   - Update `README.md` with deployment instructions for each option.

**Next Steps for the Agent**
- Create the IaC files and scripts listed above.
- Add the new CDD documents to `docs/`.
- Ensure the MCP server launches with `uv` (already adjusted in `launch_server.sh`).
- Run the test suite; fix any failures.
- Deploy to a staging AWS environment and verify end‑to‑end alert flow.

**Open Questions**
- Preferred IaC tool (Terraform vs. CDK) for the team?
- Desired notification channel hierarchy (SMS → email → Slack) if Twilio fails?
- Frequency of budget cache refresh beyond the heuristic run (e.g., background updater?).

*Generated with Claude Code*