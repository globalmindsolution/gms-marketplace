---
description: >-
  A standing run with `--suite smoke` against a repo configuring three suites,
  where `unit` and `e2e` are red and `smoke` is green. The skill should run
  only the named suite, find it green, and mint nothing -- the red suites it
  was told not to run are not its business on this run.
expected_outcome: >-
  A test-runs/run-*/results.json artifact; the run-e2e-tests step finished;
  no regression ticket; a reply reporting 1 of 1 suites passed; no questions.
tags: [behaviour]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:run-e2e-tests skill with `--suite smoke`: run only the smoke
suite, as a quick post-deploy check, record the result and handle it the way
the skill does. This is a standing run, not tied to a ticket. Do not change
any code or test. I am not available to answer questions: do not ask me
anything, make any call you need to and note it in your report.
