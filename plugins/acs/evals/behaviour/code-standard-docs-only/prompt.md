---
description: >-
  /acs:code on a docs-only ticket whose approved plan records delivery_path
  standard with two disjoint documentation partitions. The code-standard leg
  runs one implementer per partition in parallel, with the TDD steps relaxed
  for the docs_only flag: the API page and the README/CHANGELOG entries are
  written, and no source or test file is created or changed.
expected_outcome: >-
  acs:code-standard invoked; docs/api/customers.md documents offset and limit;
  the README links it; a sliced implementer-2.json report exists; no new
  src/ or tests/ module; src/shop/__init__.py unchanged; the code step's
  state.json records completed.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:code skill for ticket EVAL-1. The ticket's implementation plan is
already written, published and approved; implement exactly what it says on the
ticket branch that is checked out now, and commit the work there. Use the
plan's own delivery path and file map as they are recorded, and do not edit or
re-approve the plan. Don't push, don't run the review or open a PR, and don't
ask me anything: every decision you need is in the ticket and the plan.
Finish the code step when you are done.
