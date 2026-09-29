---
description: >-
  /acs:setup keeping every default format, adding the convention check to
  CI, and turning on the local commit-message check (off by default). Only
  that toggle is written to .acs/settings.json; the convention workflow and
  its checker are installed; branch protection is described, never changed.
expected_outcome: >-
  .acs/settings.json holds enforcement.checks.commit_message true and no
  formats; .github/workflows/acs-conventions.yml and
  .acs/ci/check-conventions.py are created; no tests or e2e gate; no
  branch-protection PUT.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:setup skill for this repo. Keep all three default formats
(branch, commit message, PR title). Add the convention check to CI, and yes,
turn on the local commit-message check as well -- we merge with merge
commits, not squash, so every commit subject should carry its ticket id. No
tests gate. I'm not an admin on the repo, so don't try to change branch
protection. Don't ask me anything.
