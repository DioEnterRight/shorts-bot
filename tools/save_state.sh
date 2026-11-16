#!/usr/bin/env bash
# Commit bot state (data/) and push it, retrying on races. FAILS LOUDLY:
# losing a push after posting would make the next run post the same video again.
set -euo pipefail
msg="$1"
git config user.name "shorts-bot"
git config user.email "shorts-bot@users.noreply.github.com"
git add data
if git diff --cached --quiet; then
  echo "No state changes to save."
  exit 0
fi
git commit -q -m "$msg"
for attempt in 1 2 3 4; do
  if git pull --rebase -q origin "${GITHUB_REF_NAME:-main}"; then
    if git push -q origin "HEAD:${GITHUB_REF_NAME:-main}"; then
      echo "State saved (attempt $attempt)."
      exit 0
    fi
  else
    git rebase --abort 2>/dev/null || true
    echo "::error::Rebase conflict while saving bot state. Someone edited data/ at the same time."
    exit 1
  fi
  sleep $((attempt * 5))
done
echo "::error::Could not push bot state after 4 attempts. Check Settings > Actions > Workflow permissions (Read and write)."
exit 1
