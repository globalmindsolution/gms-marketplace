---
description: >-
  ADR-0137's ask. The customer-listing feature's living API document
  (docs/architecture/lld/customer-listing/api/customers.md) is approved, v1,
  and describes GET /customers without a total; EVAL-1's change, left
  uncommitted on main, adds a total field to the response. The gap analyst
  finds total undocumented on an approved document, so docs-sync may not
  rewrite it: the grouped ask offers (a) update the document and send it back
  for re-approval or (b) keep it, the code being wrong. The user is
  unreachable, so the question stays open and the step stops for input.
expected_outcome: >-
  customers.md still reads status approved, version 1, and does not mention
  total; clarifications.json holds an open docs-sync question; run.json
  records docs-sync interrupted with stop_reason needs_input; the reply names
  the total field and both answers (update and re-approve, or keep); nothing
  committed and no branch created or switched.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2700
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:docs-sync skill for ticket EVAL-1. The code change is done and
left uncommitted in the working tree on main; bring whatever docs it requires
in line with it, including the feature's design documents. Leave your doc
changes uncommitted too -- do not create a branch, commit, push or open a PR.
I am not available to answer questions during this run, so do not ask me
anything; where a decision is mine to make, do not make it for me -- leave it
open and tell me in your report what you need from me.
