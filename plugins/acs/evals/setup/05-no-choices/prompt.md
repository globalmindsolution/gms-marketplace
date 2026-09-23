---
description: >-
  A bare request with no choices in it. The eval session cannot answer
  questions, so the right outcome is setup asking about the formats and CI and
  writing nothing yet.
expected_outcome: >-
  Nothing written; the reply asks about formats and CI gates, and never about
  a ticket prefix or a workspace.
tags: [setup]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

Set up acs for this repo.
