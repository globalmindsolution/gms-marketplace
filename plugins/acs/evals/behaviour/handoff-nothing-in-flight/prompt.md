---
description: >-
  The user asks to hand off EVAL-1's run, but nothing is in flight: /acs:code
  finished and recorded completed, no step is in progress. handoff should run
  handoff.py, write no flush file and finalize nothing, say plainly there is
  nothing to hand off, and still print the continue command it returns
  (/acs:ship EVAL-1).
expected_outcome: >-
  No handoff-context.md anywhere; run.json still has code completed and no
  step interrupted; the reply says nothing was in flight / nothing to hand off
  and gives /acs:ship EVAL-1; no questions.
tags: [behaviour]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

I'm stopping for the day. Run the /acs:handoff skill for ticket EVAL-1 so I
can pick it up in a fresh session tomorrow. There is nothing new to carry
over from today beyond what is already recorded. Do not start or implement
anything. I am not available to answer questions: do not ask me anything.
