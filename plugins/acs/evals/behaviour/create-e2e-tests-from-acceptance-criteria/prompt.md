---
description: >-
  A ticket whose code is done on its branch, in a repo with a configured e2e
  suite and harness, but with no test-cases.md: /acs:create-test-docs never
  ran. The skill should fall back to the ticket's two acceptance criteria,
  write one suite whose tests carry AC-1 and AC-2, commit it on the same
  ticket branch, and say no case document existed.
expected_outcome: >-
  A new tests/e2e/test_*.py suite committed as a new EVAL-1 commit on
  task/EVAL-1-serve-the-customer-listing-over-http; the step's result records
  cases_covered AC-1 and AC-2; no test-cases.md and no product code created;
  the reply notes there was no case document; no questions.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-e2e-tests skill for ticket EVAL-1. The implementation is
already done and committed on the ticket branch. The e2e suite is already
configured in .acs/settings.json; use the existing harness in tests/e2e/
exactly as it is, with no new runner or dependency. Commit the suite on the
ticket branch and do not push. I am not available to answer questions: do not
ask me anything, make any call you need to and note it in your report.
