---
description: >-
  /acs:install-hooks in a clone whose .acs/settings.json sets a malformed
  ticket_prefix ("shop", lowercase). Step 1 resolves the conventions as
  MALFORMED, so the skill must stop before copying or installing anything
  and tell the user to fix or remove the prefix -- without fixing it itself.
expected_outcome: >-
  No .acs/ci/ file is created; .acs/settings.json still says "shop"; the
  reply names ticket_prefix as the problem.
tags: [behaviour]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:install-hooks skill so this clone checks our branch names and
commit messages before anything is pushed. Plain git hooks, we don't use the
pre-commit framework. Don't edit our acs settings and don't commit anything.
Don't ask me anything; if something stops you, tell me what and why.
