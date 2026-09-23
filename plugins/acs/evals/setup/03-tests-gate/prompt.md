---
description: >-
  A terse ask for the tests-and-coverage gate on a Python repo. Setup has to
  supply a command that runs the suite and enforces the coverage target, or
  the gate fails every PR.
expected_outcome: >-
  settings.json holds a pytest tests.command enforcing $ACS_COVERAGE;
  acs-tests.yml installed; no convention workflow.
tags: [setup]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

Add the acs tests-and-coverage gate to CI for this repo. Nothing else needs to
change.
