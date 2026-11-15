---
description: >-
  A ticket whose code is done -- uncommitted on main, as /acs:code leaves it
  (ADR-0127) -- in a repo with a configured e2e suite and harness, but with no
  test-cases.md: /acs:create-test-docs never ran. The skill should fall back
  to the ticket's two acceptance criteria, write one suite whose tests carry
  AC-1 and AC-2, leave it uncommitted (no branch, no commit), and say no case
  document existed.
expected_outcome: >-
  A new tests/e2e/test_*.py suite left uncommitted (nothing committed, HEAD
  still main); the step's result records cases_covered AC-1 and AC-2; no
  test-cases.md and no product code created; the reply notes there was no case
  document; no questions.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-e2e-tests skill for ticket EVAL-1. The implementation is
already done and left uncommitted in the working tree on main. The e2e suite
is already configured in .acs/settings.json; use the existing harness in
tests/e2e/ exactly as it is, with no new runner or dependency. Leave the suite
uncommitted -- do not create a branch, commit or push. I am not available to
answer questions: do not ask me anything, make any call you need to and note
it in your report.
