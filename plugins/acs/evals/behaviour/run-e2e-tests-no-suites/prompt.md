---
description: >-
  A ticket-scoped run against a repo whose acs settings configure no suite at
  all. The skill should find nothing to run, say so plainly, still write the
  empty results artifact, and finish the step completed with the no-suite
  outcome -- not fail, and not invent or configure a runner.
expected_outcome: >-
  The EVAL-1 run's run-e2e-tests result completed with outcome no_harness (or
  nothing_to_run); a test-runs/run-*/results.json artifact; .acs/settings.json
  still configures no suites; no test file and no ticket created; a reply
  saying there was nothing to run; no questions.
tags: [behaviour]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:run-e2e-tests skill for ticket EVAL-1 and record what it finds.
Do not configure, add or change any suite, test or code. I am not available
to answer questions: do not ask me anything, make any call you need to and
note it in your report.
