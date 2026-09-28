---
description: >-
  /acs:create-impl-plan on an analyzed story whose published analysis declares
  api_surface false (log a warning when a customer listing is slow -- operator
  output, no change to GET /customers' parameters, response or errors). The
  skill should publish plan.md ending in the Contract block with
  owes.api_contract false and a reason, declare the executor file map through
  `acs.py filemap set`, and close its step, without asking anything.
expected_outcome: >-
  docs/tickets/EVAL-1/plan.md exists with a Contract block whose
  owes.api_contract is false and whose file map names src/shop/__init__.py;
  the code step's iteration-1 filemap.json names src/shop/__init__.py; the
  step's state.json records the run completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-impl-plan skill for ticket EVAL-1 (log slow customer
listings). The analysis is already published on the ticket branch that is
checked out. Take the skill all the way through: plan published to the
ticket's docs folder and committed on that branch, the executor file map
declared, and the step finished.

I can't answer questions during this run, so don't ask me anything. Every
open point is settled in docs/tickets/EVAL-1/analysis.md. The tests are
pytest under tests/, and the coverage target is the repo's configured 90%.
