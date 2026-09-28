---
description: >-
  /acs:create-test-docs on a docs-only ticket whose completed planning step
  owes no test cases (owes.test_cases false, with a reason). The pre-hook
  settles the step as an evidenced no-op, outcome no_cases_owed, and refuses
  the invocation: no test-designer runs, no test-cases.md is written, and the
  reply relays what was recorded.
expected_outcome: >-
  run.json records create-test-docs completed with outcome no_cases_owed; no
  test-cases.md and nothing under tests/ were created; the final reply says
  the step had nothing to do.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-test-docs skill for ticket EVAL-1 (document how to run
the tests). The implementation plan is already published on the ticket branch
that is checked out.

I can't answer questions during this run, so don't ask me anything. If this
step has nothing to do for this ticket, don't write anything — just tell me
what it recorded.
