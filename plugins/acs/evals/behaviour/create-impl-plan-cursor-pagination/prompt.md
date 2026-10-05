---
description: >-
  /acs:create-impl-plan on an analyzed story (cursor pagination for GET
  /customers) whose API contract was approved in the Design phase. The skill
  should read that contract as a binding input, publish plan.md to the
  ticket's docs folder naming the contract it implements and ending in the
  machine-read Contract block -- delivery path, owes flags (test cases, e2e;
  no API contract step) and the executor file map -- declare that file map
  through `acs.py filemap set`, and close its step, without asking anything.
expected_outcome: >-
  docs/development/customer-listing/EVAL-1/plan.md exists with a Contract block (delivery_path,
  owes without api_contract, an Executor tasks & file map naming
  src/shop/__init__.py) and the 90% coverage target; the code step's
  iteration-1 filemap.json names src/shop/__init__.py; the step's state.json
  records the run completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-impl-plan skill for ticket EVAL-1 (cursor pagination for
GET /customers). The analysis is already published in the ticket's docs
folder, uncommitted, on main. Take the skill all the way through: plan
published to the ticket's docs folder and left uncommitted (no branch, no
commit: /acs:create-pr commits later), the executor file map declared, and the
step finished.

I can't answer questions during this run, so don't ask me anything. Every
open point is already settled in docs/development/customer-listing/EVAL-1/analysis.md. The tests
are pytest under tests/, and the coverage target is the repo's configured
90%. If the plan looks large, keep it as one pull request — do not split the
ticket.
