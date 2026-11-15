---
description: >-
  /acs:create-test-docs on a story with three acceptance criteria, a plan that
  owes test cases and an API contract with an invalid_cursor error. The skill
  should publish test-cases.md with its machine-read front matter and four
  sections, a TC table tracing every criterion and covering the contract's
  error, write no test or production code, and close its step with outcome
  cases_written -- without asking anything.
expected_outcome: >-
  docs/development/customer-listing/EVAL-1/test-cases.md exists with integer cases and e2e_cases in
  the front matter, the four headings in order, TC rows citing AC-1, AC-2 and
  AC-3 and a row expecting invalid_cursor; nothing under src/ or tests/ was
  created; run.json records the step completed with outcome cases_written.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-test-docs skill for ticket EVAL-1 (cursor pagination for
GET /customers). The analysis, the implementation plan and the API contract
are already published in the ticket's docs folder, uncommitted, on main. Take
the skill all the way through: test cases published to the ticket's docs
folder and left uncommitted (no branch, no commit: /acs:create-pr commits
later), and the step finished.

I can't answer questions during this run, so don't ask me anything. Each of
the three acceptance criteria means what it says; the tests are pytest under
tests/, and this ticket has no e2e suite — the plan owes no e2e.
