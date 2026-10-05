---
description: >-
  /acs:handoff in send mode with nothing to send (ADR-0131): the checkout has
  no run and no ticket, and the user names none. The skill must resolve the
  ticket from this checkout's run, find there is none, push nothing, and say
  so -- never guess an id or package the bare working tree.
expected_outcome: >-
  No ref under .eval-origin.git/refs/ is created and no branch is pushed; no
  ticket or run is created in the workspace; HEAD is still the scaffold's
  commit; the reply says there is nothing to hand off and points at
  /acs:handoff <ticket-id>; no questions.
tags: [behaviour]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, AskUserQuestion]
---

Run the /acs:handoff skill: hand whatever I'm working on in this checkout to
Minh, he'll carry on from his machine. I don't remember the ticket number. I am
not available to answer questions: do not ask me anything.
