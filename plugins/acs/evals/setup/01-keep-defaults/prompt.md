---
description: >-
  Every choice is stated: keep the default formats, install no CI. Setup
  should apply that without asking, write no settings file, and still put its
  ignore entries in place.
expected_outcome: >-
  No .acs/settings.json, no CI files, .gitignore carries the
  settings.local.json entry, no stray answers file, no questions.
tags: [setup]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

Set up acs in this repo. Keep the default branch, commit and PR title formats,
and don't install any CI checks.
