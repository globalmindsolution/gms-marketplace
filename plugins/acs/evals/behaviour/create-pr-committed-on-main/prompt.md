---
description: >-
  EVAL-1 is implemented and already committed -- straight on main, never
  pushed -- and its /acs:code run is recorded, so the commit plan has no
  uncommitted group to propose but reports the commit as ahead of origin. create-pr
  must still ship it: cut a feature branch at HEAD with `acs.py pr commit` (the work
  is never left to be pushed from main), then meet gh unable to reach a forge at the
  critical base detection, push nothing, record the failure with the branch and no
  PR, and say so.
expected_outcome: >-
  HEAD ends on a new task/EVAL-1-* branch cut at the existing commit; nothing
  reached the local origin beyond the scaffold's main; steps/create-pr/state.json
  records a failed invocation naming that branch, whose errors name the failed gh
  call, with no pr object; the reply says gh was unavailable and no PR was opened.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-pr skill for ticket EVAL-1 — the implementation is done and
already committed, on main, and not pushed. Get it into a pull request against
the default branch the way the skill does, and tell me where it stands. Do not
ask me anything; I will not be able to answer.
