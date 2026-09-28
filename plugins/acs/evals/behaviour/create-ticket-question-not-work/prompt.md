---
description: >-
  A question about the backlog phrased next to create-ticket's vocabulary (is
  there already a ticket for cursor pagination, and how many acceptance
  criteria does it carry) on a repo whose workspace already holds that ticket.
  Nothing new is being asked for, so /acs:create-ticket must not run and
  nothing may be minted; the reply answers from the existing ticket.
expected_outcome: >-
  No Skill call names create-ticket; no EVAL-2 partition or docs folder is
  created; the final reply names EVAL-1 and its three acceptance criteria.
tags: [behaviour]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Quick question before I decide whether there is any new work here: do we
already have an acs ticket for cursor pagination on GET /customers? If we do,
tell me its id and how many acceptance criteria it has. I'm only asking —
I haven't decided to file anything, so don't create or change any ticket.
