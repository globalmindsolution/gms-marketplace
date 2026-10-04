---
description: >-
  /acs:create-test-docs on a task whose criteria are HTTP behaviour against
  the running app (two of three), in a repo with a configured e2e suite
  (tests/e2e/, an in-process WSGI harness) and a plan that owes e2e. The skill
  should type those cases e2e -- the bare word in the Type cell the
  create-e2e-tests gate counts -- with e2e_cases in the front matter and the
  result matching the table, target the e2e suite, write no test code, and
  close with outcome cases_written.
expected_outcome: >-
  docs/tickets/EVAL-1/test-cases.md exists with at least one TC row whose Type
  cell is exactly e2e and a positive integer e2e_cases in the front matter;
  the step state records a positive e2e_cases; run.json records the step
  completed with outcome cases_written; nothing under src/ or tests/ was
  created.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-test-docs skill for ticket EVAL-1 (serve the customer
listing over HTTP). The implementation plan is already published in the
ticket's docs folder, uncommitted, on main. Take the skill all the way
through: test cases published to the ticket's docs folder and left uncommitted
(no branch, no commit: /acs:create-pr commits later), and the step finished.

I can't answer questions during this run, so don't ask me anything. The
first two criteria are about the running HTTP app and belong in this repo's
e2e suite (tests/e2e/, configured as the `e2e` suite); the third is a plain
unit-level check. Unit tests are pytest under tests/unit/.
