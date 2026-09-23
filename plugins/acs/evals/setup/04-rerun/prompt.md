---
description: >-
  Setup run again on a repo it configured before, by a user who wants nothing
  changed. A re-run must be a visible no-op.
expected_outcome: >-
  The seeded pr_title survives, .gitignore carries its entry once, no new gate
  appears, and the reply reports nothing changed.
tags: [setup]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

I set acs up in this repo a while ago. Run setup again and make sure
everything is still in place -- I don't want to change anything.
