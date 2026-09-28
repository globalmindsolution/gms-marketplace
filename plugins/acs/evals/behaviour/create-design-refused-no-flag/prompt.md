---
description: >-
  /acs:create-design asked for a story that was minted with needs_design false
  (show the app version on GET /health). The pre-hook refuses: create-design
  only runs for design-significant tickets. The refusal must stand -- no step
  opened, no design written, the ticket's flag left alone -- and the reply
  must relay it and point at /acs:code.
expected_outcome: >-
  No design.md and no create-design step state are created; the ticket keeps
  needs_design false; the final reply names the needs_design refusal and
  /acs:code EVAL-1.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-design skill for ticket EVAL-1 (show the app version on
GET /health).

I can't answer questions during this run, so don't ask me anything; if the
skill will not run for this ticket, tell me why and what to run instead.
