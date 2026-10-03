---
description: >-
  A bare request with no choices in it. The eval session cannot answer
  questions, so the right outcome is setup asking about the ticket prefix, CI and
  the model settings and writing nothing yet.
expected_outcome: >-
  Nothing written; the reply asks about the ticket prefix and CI gates, and never about
  a workspace.
tags: [setup]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

Set up acs for this repo.
