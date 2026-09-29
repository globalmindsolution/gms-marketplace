---
description: >-
  /acs:code on a trivial-path plan whose red test is already on main: the
  greeting typo is fixed in the one mapped module, while the same typo in
  src/shop/emails.py -- out of scope and outside the plan's file map -- is
  left untouched.
expected_outcome: >-
  acs:code-trivial invoked; greeting() says "Hello"; src/shop/emails.py still
  says "Helo from shop"; no sliced implementer report; the code step's
  state.json records completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:code skill for ticket EVAL-1. The ticket's implementation plan is
already written and published; implement exactly what it says, test-first, on
the ticket branch that is checked out now, and commit the work there. Use the
plan's own delivery path and file map as they are recorded, and change nothing
outside that file map. Don't push, don't run the review or open a PR, and
don't ask me anything: every decision you need is in the ticket and the plan.
Finish the code step when you are done.
