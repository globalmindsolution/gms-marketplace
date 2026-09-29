---
description: >-
  A standing run against a repo configuring two suites: `unit` passes, `e2e`
  has one failing test (it expects 50 per page; the product pages by 20). The
  skill should run both, write its results artifact, and on the failure mint
  one regression ticket keyed to the failing e2e test -- and none for the
  passing suite.
expected_outcome: >-
  A test-runs/run-*/results.json artifact; regression ticket EVAL-1 whose
  description carries `acs-regression-key: e2e:...test_customers_default_page_is_50`
  and links the results artifact; no EVAL-2; a reply reporting 1 of 2 suites
  passed; no questions.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:run-e2e-tests skill against this repo: run every configured
suite, record the results, and handle any failure the way the skill does. This
is a standing run, not tied to a ticket. Do not fix any code or test. I am not
available to answer questions: do not ask me anything, make any call you need
to and note it in your report.
