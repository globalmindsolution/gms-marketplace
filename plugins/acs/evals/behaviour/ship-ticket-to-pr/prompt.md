---
description: >-
  A seeded, well-specified task (EVAL-1: cap the customer page size at 100)
  shipped with one command. ship must drive workflows/ship.yaml from the run's
  cursor -- analyze-requirements through run-e2e-tests all completed, the cap
  implemented (left uncommitted -- only create-pr branches and commits,
  ADR-0127) and reviewed -- and reach create-pr, which fails at its critical
  gh base detection before any push. ship must stop there, report the failed
  step and how to resume, and never merge.
expected_outcome: >-
  run.json records the nine steps before create-pr completed and create-pr
  failed; create-pr's state carries a gh error and no pr object; review-code
  derived verifier_passed true; src/shop/__init__.py enforces the 100 cap; no
  branch reached the local origin; no gh pr merge was run.
tags: [behaviour]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Use the /acs:ship skill to ship ticket EVAL-1 end to end, up to its pull
request. The ticket carries everything you need; where a step would ask me
something, decide it yourself from the ticket and record it as an assumption.
Do not ask me anything; I will not be able to answer.
