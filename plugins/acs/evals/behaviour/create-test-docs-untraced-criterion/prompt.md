---
description: >-
  /acs:create-test-docs on a story whose fourth acceptance criterion has no
  observable outcome (the pagination code is clean and easy to maintain) and
  whose author is unreachable. The documented arm: every other criterion is
  traced, AC-4 is neither dropped nor covered by a fake case, the gap is
  published and recorded as an open ledger question, and the step stops for
  input with untraced_acs naming AC-4.
expected_outcome: >-
  docs/tickets/EVAL-1/test-cases.md exists, names AC-4 under Gaps and
  assumptions and has no TC row for AC-4; clarifications.json holds an open
  create-test-docs question; the step state records untraced_acs [AC-4];
  run.json records the step interrupted with stop_reason needs_input.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-test-docs skill for ticket EVAL-1 (cursor pagination for
GET /customers). The analysis, the implementation plan and the API contract
are already published in the ticket's docs folder, uncommitted, on main. Take
the skill as far as it can honestly go: test cases published to the ticket's
docs folder and left uncommitted (no branch, no commit: /acs:create-pr commits
later), and the step finished.

I can't answer questions during this run, so don't ask me anything. The
first three acceptance criteria mean what they say; the tests are pytest
under tests/ and there is no e2e suite. The fourth one ("clean and easy to
maintain") was written by someone who is away, and I don't know what they
meant to measure — don't invent a measure for it.
