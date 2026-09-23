---
description: >-
  Should NOT fire: repo tooling setup that is not about acs.
expected_outcome: >-
  acs:setup is never invoked; a pre-commit config is written; no acs files.
tags: [setup]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

Set up pre-commit for this repo with black and ruff hooks.
