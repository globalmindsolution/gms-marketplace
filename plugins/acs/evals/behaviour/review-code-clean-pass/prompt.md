---
description: >-
  /acs:review-code on a ticket whose changeset -- uncommitted on main, as
  /acs:code leaves it -- is clean: a negative page offset is refused, both
  acceptance criteria are tested, and the README and CHANGELOG say so. No
  candidate finding survives adjudication, the final gate runs, and the kernel
  derives a pass from a verdict with no blocking finding.
expected_outcome: >-
  verdict.json written; iter-<n>/gate.json written; the kernel derives 0
  blocking findings; source untouched; no new source or test module.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:review-code skill on ticket EVAL-1: review EVAL-1's change, which
/acs:code left uncommitted in the working tree on main (nothing is committed
before /acs:create-pr). Review only; don't fix anything, don't run /acs:code,
and don't push. Don't ask me anything: the ticket's acceptance criteria are
the requirements, and there is no separate plan or design. Finish the review
step and tell me what you found.
