---
description: >-
  /acs:code on a ticket whose approved plan records delivery_path trivial. The
  prompt never names the path: /acs:code must read it from the plan and
  dispatch the code-trivial leg, whose one implementer corrects the constant
  test-first and finishes the code step.
expected_outcome: >-
  acs:code-trivial invoked; PAGE_SIZE is 25; tests/test_page_size.py created;
  no sliced implementer report; the code step's state.json records completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:code skill for ticket EVAL-1. The ticket's implementation plan is
already written and published; implement exactly what it says, test-first, on
the ticket branch that is checked out now, and commit the work there. Use the
plan's own delivery path and file map as they are recorded. Don't push, don't
run the review or open a PR, and don't ask me anything: every decision you
need is in the ticket and the plan. Finish the code step when you are done.
