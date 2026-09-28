---
description: >-
  /acs:code on a ticket whose approved plan records delivery_path small. The
  prompt never names the path: /acs:code must read it from the plan and
  dispatch the code-small leg, which implements the planned guard test-first
  and finishes the code step.
expected_outcome: >-
  acs:code-small invoked; src/shop/__init__.py raises ValueError on a negative
  offset; tests/test_list_customers.py created; the code step's state.json
  records completed.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:code skill for ticket EVAL-1. The ticket's implementation plan is
already written and published; implement exactly what it says, test-first, on
the ticket branch that is checked out now, and commit the work there. Use the
plan's own delivery path and file map as they are recorded. Don't push, don't
run the review or open a PR, and don't ask me anything: every decision you
need is in the ticket and the plan. Finish the code step when you are done.
