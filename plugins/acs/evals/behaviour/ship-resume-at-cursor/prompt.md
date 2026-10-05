---
description: >-
  A /acs:ship run over EVAL-1 stopped part-way: analyze-requirements through
  run-e2e-tests are recorded completed (the cap left uncommitted on main, the
  review passed), so the run's cursor is create-pr. Asked to carry on, ship
  must resume AT the cursor -- run create-pr, which fails at its critical gh
  base detection before any push -- and re-run nothing before it. It stops on
  the failure, reports how to resume, and never merges.
expected_outcome: >-
  Every earlier step's state still carries exactly one invocation and run.json
  still records all eight completed; create-pr is recorded failed with a gh
  error and no pr object; nothing reached the local origin; no gh pr merge
  was run.
tags: [behaviour]
max_turns: 80
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

My earlier session shipping ticket EVAL-1 with /acs:ship stopped part-way.
Use the /acs:ship skill to pick EVAL-1 up from where it left off and take it
to its pull request. Do not ask me anything; I will not be able to answer.
