#!/usr/bin/env bash
# invoke-bot.sh — Launch an identity-isolated Claude Code session on the Mecris fork.
#
# The bot has NO access to your personal ~/.gitconfig identity or credentials.
# It commits as mecris-bot and pushes only to the fork remote via deploy key.
#
# Usage:
#   ./scripts/invoke-bot.sh                      # interactive session
#   ./scripts/invoke-bot.sh "fix the lint errors" # headless prompt

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOY_KEY="${HOME}/.ssh/mecris_bot_deploy_key"
BOT_SECRETS="${HOME}/.mecris-bot.env"
FORK_REMOTE="${MECRIS_BOT_FORK_REMOTE:-git@github.com:yebyen/mecris.git}"
BOT_NAME="mecris-bot"
BOT_EMAIL="mecris-bot@noreply"

# --- Load bot secrets (GITHUB_TOKEN etc) ---
if [[ -f "${BOT_SECRETS}" ]]; then
  # shellcheck source=/dev/null
  set -a; source "${BOT_SECRETS}"; set +a
fi

# --- Validate ---
if [[ ! -f "${DEPLOY_KEY}" ]]; then
  echo "ERROR: Deploy key not found at ${DEPLOY_KEY}" >&2
  exit 1
fi

# FORK_REMOTE has a default; this guard is just a safety net
if [[ -z "${FORK_REMOTE}" ]]; then
  echo "ERROR: MECRIS_BOT_FORK_REMOTE is not set." >&2
  exit 1
fi

# --- Bot environment ---
export GIT_AUTHOR_NAME="${BOT_NAME}"
export GIT_AUTHOR_EMAIL="${BOT_EMAIL}"
export GIT_COMMITTER_NAME="${BOT_NAME}"
export GIT_COMMITTER_EMAIL="${BOT_EMAIL}"
export GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"

# Ensure the fork remote is registered (idempotent)
if ! git -C "${REPO_DIR}" remote get-url bot-fork &>/dev/null; then
  git -C "${REPO_DIR}" remote add bot-fork "${FORK_REMOTE}"
  echo "Registered remote 'bot-fork' -> ${FORK_REMOTE}"
else
  current=$(git -C "${REPO_DIR}" remote get-url bot-fork)
  if [[ "${current}" != "${FORK_REMOTE}" ]]; then
    git -C "${REPO_DIR}" remote set-url bot-fork "${FORK_REMOTE}"
    echo "Updated remote 'bot-fork' -> ${FORK_REMOTE}"
  fi
fi

echo "Bot identity: ${BOT_NAME} <${BOT_EMAIL}>"
echo "Fork remote:  ${FORK_REMOTE}"
echo "Deploy key:   ${DEPLOY_KEY}"
echo ""

PROMPT="${1:-}"

if [[ -n "${PROMPT}" ]]; then
  # Headless mode: pass prompt directly to claude
  exec claude --dangerously-skip-permissions -p "${PROMPT}" --workspace "${REPO_DIR}"
else
  # Interactive mode
  exec claude --workspace "${REPO_DIR}"
fi
