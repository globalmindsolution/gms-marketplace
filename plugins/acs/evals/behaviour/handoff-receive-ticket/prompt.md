---
description: >-
  /acs:handoff in receive mode (ADR-0131): Lan sent EVAL-1 from her machine to
  refs/acs/handoff/EVAL-1 on origin, with her work uncommitted, the code step
  in flight and a note carrying a decision nothing else records. This clean
  checkout has no EVAL-1 state. The skill should receive it with `acs.py
  handoff receive EVAL-1`, show Lan's note and print `continue_with` -- never
  commit, branch or open a PR (ADR-0127).
expected_outcome: >-
  tests/test_page_cap.py appears and src/shop/__init__.py carries the clamp,
  both uncommitted; the ticket and run.json for EVAL-1 are restored under
  .acs/state-machine/example-shop/ with the code step in_progress; no commit
  on HEAD; the reply shows the note's clamp-not-400 decision and /acs:code
  EVAL-1; no questions.
tags: [behaviour]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, AskUserQuestion]
---

Run the /acs:handoff skill to pick up ticket EVAL-1 from Lan: she handed it
over to me before going on leave. Show me her note and tell me what to run
next. Do not implement or change anything yourself. I am not available to
answer questions: do not ask me anything.
