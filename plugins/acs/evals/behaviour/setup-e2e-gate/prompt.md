---
description: >-
  /acs:setup on a repo whose e2e suite is already configured in
  .acs/settings.json, asked to add only the e2e merge gate. setup must
  install the e2e runner and workflow (and nothing else), keep the suite
  definition, and name the `E2E suite` required check without changing
  branch protection.
expected_outcome: >-
  .acs/ci/run-e2e.py and .github/workflows/acs-e2e.yml are created; no
  conventions or tests gate; .acs/settings.json still defines suites.e2e;
  the reply names the `E2E suite` check.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:setup skill: we already configured our e2e suite for acs, and
now I want acs's e2e merge gate in CI so a red e2e run blocks the PR. Keep
the ticket prefix as it is and don't add any other CI check. I'm not an admin, so
don't touch branch protection -- just tell me what an admin needs to do.
Don't ask me anything.
