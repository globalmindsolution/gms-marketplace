---
description: >-
  A standing run where the e2e suite fails before any test runs (a syntax
  error in the product), so its regression key is the `e2e:__suite__`
  fallback -- and an open ticket, EVAL-1, already carries that exact key from
  an earlier run. The skill should comment-bump EVAL-1 with this run's
  evidence and mint nothing.
expected_outcome: >-
  A test-runs/run-*/results.json artifact; EVAL-1's description keeps its
  original text and gains this run's evidence (its run id); EVAL-1 stays open;
  no EVAL-2; the reply names EVAL-1 as the ticket updated; no questions.
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
