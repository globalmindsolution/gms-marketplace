---
description: >-
  /acs:install-hooks in a fresh clone of a repo whose .acs/ci/ files are
  already committed and whose clone has no git hooks yet. It must install
  both the commit-msg and pre-push hooks with the committed installer, use
  plain git hooks (no pre-commit framework in this repo), and tell the user
  nothing new needs committing.
expected_outcome: >-
  .git/hooks/commit-msg and .git/hooks/pre-push both run
  .acs/ci/check-conventions.py; no .pre-commit-config.yaml is created; the
  reply says both hooks were installed.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

I just cloned this repo. Run the /acs:install-hooks skill so my clone checks
branch names and commit messages locally the way the team configured. We
don't use the pre-commit framework. Don't commit anything, and don't ask me
anything -- just tell me what you set up.
