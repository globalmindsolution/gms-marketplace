---
description: >-
  A ticket whose code is done -- uncommitted on main, as /acs:code leaves it
  (ADR-0127) -- with a test-cases.md typing two of its three cases e2e and a
  configured e2e suite (a stdlib unittest harness under tests/e2e/). The skill
  should write one suite covering exactly the e2e cases, in the repo's
  harness, and leave it uncommitted -- no branch, no commit.
expected_outcome: >-
  A new tests/e2e/test_*.py suite covering TC-2 and TC-3 (not the unit TC-1),
  left uncommitted (nothing committed, HEAD still main), the step's result
  recording cases_covered TC-2 and TC-3, no product code written, no
  questions.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-e2e-tests skill for ticket EVAL-1. The implementation is
already done and left uncommitted in the working tree on main, and the
ticket's test cases are in its test-cases.md. The e2e suite is already
configured in .acs/settings.json; use the existing harness in tests/e2e/
exactly as it is, with no new runner or dependency. Leave the suite
uncommitted -- do not create a branch, commit or push. I am not available to
answer questions: do not ask me anything, make any call you need to and note
it in your report.
