---
description: >-
  /acs:create-ticket asked for purely technical work (move the test runner to
  Python 3.13 and drop 3.11) in a repo with no PRD. A technical task needs no
  PRD and links nothing (ADR-0144), so the skill mints one task, unlinked, and
  completes -- it does not refuse for want of a PRD, nor invent a feature.
expected_outcome: >-
  EVAL-1's ticket.json is type task with no features; the create-ticket step
  state records completed; the reply names EVAL-1.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-ticket skill with this request:

Move our test runner from Python 3.11 to 3.13 and drop 3.11 support from the
CI matrix. It is pure maintenance -- nothing a customer will notice.

I can't answer questions during this run, so don't ask me anything. Use your
judgement for the rest of the record -- title, description, priority and the
acceptance criteria are yours to decide, no need to confirm them.
