---
description: >-
  EVAL-1's /acs:code step is completed and /acs:review-code is in flight
  (started through acs.py, lock held) when the user asks to hand off, giving
  one review decision to carry over. handoff should flush that soft context
  under the REVIEW step, finalize review-code interrupted through handoff.py,
  leave code completed, and print /acs:review-code EVAL-1.
expected_outcome: >-
  run.json's review-code step interrupted with stop_reason context_pressure
  and code still completed; review-code's invocation finalized with a handoff
  summary; the decision (negative limits out of scope, own ticket) in
  steps/review-code/handoff-context.md; the reply gives /acs:review-code
  EVAL-1 and says the lock was released; no questions.
tags: [behaviour]
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

We are halfway through reviewing EVAL-1 and this session has grown too long.
Run the /acs:handoff skill for the run in flight (ticket EVAL-1) so the review
can be finished in a fresh session. Carry over what we decided during the
review, which is not written down anywhere yet: a negative limit is out of
scope for EVAL-1 and gets its own ticket later, so it must not be raised as a
blocking finding here; the cap test in tests/test_page_cap.py has been read
and is fine; what remains is reviewing the change in src/shop/__init__.py.
Do not review, fix or implement anything now. I am not available to answer
questions: do not ask me anything.
