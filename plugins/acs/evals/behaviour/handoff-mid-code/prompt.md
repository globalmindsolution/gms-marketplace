---
description: >-
  EVAL-1's /acs:code step is in flight (started through acs.py, lock held, a
  failing test committed) and the user asks to hand the work off to a fresh
  session, giving one decision to carry over. handoff should flush that soft
  context, finalize the step interrupted through handoff.py, and print the
  continue command.
expected_outcome: >-
  run.json's code step interrupted with stop_reason context_pressure; the code
  step's invocation finalized with a handoff summary; the decision
  (clamp to 100, no 400) in steps/code/handoff-context.md; the reply gives
  /acs:code EVAL-1 and says the lock was released; no questions.
tags: [behaviour]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

This session has grown too long. Run the /acs:handoff skill for the run in
flight (ticket EVAL-1) so I can continue it in a fresh session tomorrow. Carry
over what we decided today, which is not written down anywhere yet: we agreed
that a limit above 100 is silently clamped to 100 rather than rejected with a
400, and the failing test in tests/test_page_cap.py is the next thing to make
pass. Do not implement anything now. I am not available to answer questions:
do not ask me anything.
