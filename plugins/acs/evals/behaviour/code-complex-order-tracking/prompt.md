---
description: >-
  /acs:code on a ticket whose approved plan records delivery_path complex with
  two partitions meeting at one seam. /acs:code must read the path from the
  plan and dispatch the code-complex leg, which runs the partition
  implementers in parallel, then the integration implementer, and finishes
  the code step.
expected_outcome: >-
  acs:code-complex invoked; src/shop/orders.py and src/shop/tracking.py
  created; advance raises ValueError; implementer-integration.json written;
  the code step's state.json records completed.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:code skill for ticket EVAL-1. The ticket's implementation plan is
already written, published and approved; implement exactly what it says, test-
first, in the working tree as it is checked out now, and leave the work
uncommitted -- no branch, no commit (/acs:create-pr commits later). Use the
plan's own delivery path and file map as they are recorded, and do not edit or
re-approve the plan. Don't push, don't run the review or open a PR, and don't
ask me anything: every decision you need is in the ticket and the plan. Finish
the code step when you are done.
