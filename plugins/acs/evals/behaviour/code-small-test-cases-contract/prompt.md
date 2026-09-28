---
description: >-
  /acs:code on a small-path plan whose run carries test-cases.md from
  /acs:create-test-docs. On this path that document is the test contract: the
  code-small leg's implementer writes one test per TC-n row, naming its TC id
  in the test's docstring, then the guard that makes them pass.
expected_outcome: >-
  acs:code-small invoked; tests/test_list_customers.py names TC-1, TC-2 and
  TC-3; src/shop/__init__.py raises ValueError; no test module named by the
  ticket id; the code step's state.json records completed.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:code skill for ticket EVAL-1. The ticket's implementation plan
and its test cases are already written and published; implement exactly what
they say, test-first, on the ticket branch that is checked out now, and commit
the work there. Use the plan's own delivery path and file map as they are
recorded. Don't push, don't run the review or open a PR, and don't ask me
anything: every decision you need is in the ticket, the plan and the test
cases. Finish the code step when you are done.
