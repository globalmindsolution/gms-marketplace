---
description: >-
  /acs:code standalone on a prompt subject, with no ticket and no plan. The
  run must derive an implicit plan from the prompt and record it under its
  own run's steps/code/, judge it onto a cheap path, implement the cap
  test-first on a branch of its own, and mint no ticket.
expected_outcome: >-
  acs:code invoked; runs/<run-id>/steps/code/plan.md created; src/shop
  caps the limit at 100; a new tests/test_*.py; no EVAL ticket minted; HEAD
  is not main.
tags: [behaviour]
max_turns: 100
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:code skill on this request, as its subject, exactly as written:
"Cap the customer page size: list_customers must never use a limit above 100;
a larger limit is clamped to 100." There is no ticket for it and I don't want
one created, and there is no plan: work from the request itself. Implement it
test-first on a branch of its own and commit it there. Don't push, don't run
the review or open a PR, and don't ask me anything. Finish the code step when
you are done.
