---
description: >-
  /acs:create-ticket on a bug report against the shipped customer listing
  (PRD F1), with every record decision given up front. The skill should type
  it a bug, have the bug author draft it and the reviewer judge the draft,
  and mint ONE ticket carrying the bug fields -- steps to reproduce, expected
  and actual behaviour, environment and a severity separate from its
  priority -- with a first acceptance criterion that a regression test
  reproduces the bug, then close its step without asking anything.
expected_outcome: >-
  EVAL-1's ticket.json is type bug with severity high, a non-empty
  reproduction, expected, actual and environment, and acceptance criteria
  opening with the regression test; the bug author and the reviewer were
  spawned; no second ticket exists; the create-ticket step records completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-ticket skill with this bug report:

The customer listing ignores the page size we ask for. Calling
`list_customers(limit=50)` in version 2.4.0 (Python 3.12, the default
settings) still pages by 20: the response says `"limit": 20` and holds at most
20 customers. It should honour any limit from 1 to 100 and return that many.

To reproduce:
1. Start from a database with 60 customers.
2. Call `list_customers(offset=0, limit=50)`.
3. Look at the response's `limit` and the number of items.

I can't answer questions during this run, so don't ask me anything. It is a
bug, severity high, priority medium, no due date. Use your judgement for the
rest of the record — title, description and the acceptance criteria are yours
to decide, no need to confirm them. Take the skill all the way through: ticket
written and the step finished.
