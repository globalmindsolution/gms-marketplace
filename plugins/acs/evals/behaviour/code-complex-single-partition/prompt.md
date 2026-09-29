---
description: >-
  /acs:code on a ticket whose approved plan records delivery_path complex for a
  security boundary that fits in one partition. The code-complex leg spawns a
  single un-sliced implementer and skips the integration pass -- there are no
  seams between partitions -- delivering salted, constant-time key
  verification test-first.
expected_outcome: >-
  acs:code-complex invoked; src/shop/auth.py uses pbkdf2/scrypt and
  hmac.compare_digest; tests/test_auth.py created; iter-1/implementer.json
  written and no implementer-integration.json; the code step's state.json
  records completed.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:code skill for ticket EVAL-1. The ticket's implementation plan is
already written, published and approved; implement exactly what it says,
test-first, on the ticket branch that is checked out now, and commit the work
there. Use the plan's own delivery path and file map as they are recorded, and
do not edit or re-approve the plan. Don't push, don't run the review or open a
PR, and don't ask me anything: every decision you need is in the ticket and
the plan. Finish the code step when you are done.
