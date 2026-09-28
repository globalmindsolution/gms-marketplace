---
description: >-
  A ticket whose code is done on its branch and whose committed test-cases.md
  types every case unit (e2e_cases 0), in a repo with a configured e2e suite.
  The skill should find nothing to write, finish completed with outcome
  no_e2e_owed, and leave the repo untouched -- no suite, no edit to the case
  document, no commit.
expected_outcome: >-
  The EVAL-1 run's create-e2e-tests result completed with outcome
  no_e2e_owed; no file created under tests/; test-cases.md still types no case
  e2e; the ticket branch has no commit after "EVAL-1 test cases"; the reply
  says no e2e case was owed; no questions.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-e2e-tests skill for ticket EVAL-1. The implementation is
done and committed on the ticket branch, and the ticket's test cases are in
its test-cases.md. The e2e suite is configured in .acs/settings.json. Do not
push. I am not available to answer questions: do not ask me anything, make any
call you need to and note it in your report.
