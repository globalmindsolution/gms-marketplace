---
description: >-
  A ticket-scoped run against a repo whose two configured suites, `unit` and
  `e2e`, both pass. The skill should run them, write its results artifact, take
  the all-green short-circuit -- no triage, no regression ticket -- and finish
  the step completed with outcome passed.
expected_outcome: >-
  A test-runs/run-*/results.json artifact; the EVAL-1 run's run-e2e-tests
  result completed with outcome passed; no ticket beyond the scaffold's EVAL-1;
  a reply reporting every suite passed; no questions.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:run-e2e-tests skill for ticket EVAL-1: run the configured suites,
record the results, and handle whatever they show the way the skill does. Do
not change any code or test. I am not available to answer questions: do not
ask me anything, make any call you need to and note it in your report.
