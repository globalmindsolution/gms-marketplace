---
description: >-
  Should NOT fire: a plain CI request that is not about acs.
expected_outcome: >-
  acs:setup is never invoked; a workflow is written; no acs files.
tags: [setup]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

Add a GitHub Actions workflow that runs the pytest suite on every push and
pull request.
