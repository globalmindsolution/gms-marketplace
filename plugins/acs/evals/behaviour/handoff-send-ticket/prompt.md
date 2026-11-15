---
description: >-
  /acs:handoff in send mode (ADR-0131): EVAL-1's /acs:code step is in flight
  with the work uncommitted, and the user hands the ticket to a teammate,
  dictating the note and confirming the push. The skill should preview the
  package, send it with `acs.py handoff send` to refs/acs/handoff/EVAL-1 on
  origin, and leave everything on the sender's machine as it was -- no
  branch, no commit, no PR (ADR-0127).
expected_outcome: >-
  .eval-origin.git/refs/acs/handoff/EVAL-1 is created and no branch is
  pushed; HEAD's reflog still ends at the scaffold's checkout (nothing
  committed); src/shop/__init__.py still carries the uncommitted clamp and
  the run's code step is still in_progress; the reply says the sender keeps
  everything and tells Minh to run /acs:handoff receive EVAL-1; no questions.
tags: [behaviour]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, AskUserQuestion]
---

Run the /acs:handoff skill to hand ticket EVAL-1 to Minh: he takes it over
tomorrow on his own machine. Use this as the note, it is final. Done: the
clamp in src/shop/__init__.py and the test in tests/test_page_cap.py. In
flight: nothing. Next: run the tests, then review the change. Decisions: a
limit above 100 is silently clamped to 100, never rejected with a 400. The
run has no attachments. I confirm the push: send it. I am not available to
answer questions: do not ask me anything.
