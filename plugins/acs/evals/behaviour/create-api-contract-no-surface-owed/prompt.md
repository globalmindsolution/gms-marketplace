---
description: >-
  /acs:create-api-contract on a ticket whose implementation plan -- produced
  by a completed create-impl-plan step -- owes no API contract (an operator
  log line; GET /customers is unchanged). The pre-hook settles the step as an
  evidenced no-op, outcome no_surface_owed, and refuses the invocation, so no
  coordinator runs and nothing is written; the reply relays what was recorded.
expected_outcome: >-
  run.json records create-api-contract completed with outcome no_surface_owed;
  no api-contract.md and no docs/api/ or OpenAPI file were created; the final
  reply says the step had nothing to do.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-api-contract skill for ticket EVAL-1 (log slow customer
listings). The analysis and the implementation plan are already published on
the ticket branch that is checked out.

I can't answer questions during this run, so don't ask me anything. If it
turns out this step has nothing to do for this ticket, don't write anything —
just tell me what it recorded.
