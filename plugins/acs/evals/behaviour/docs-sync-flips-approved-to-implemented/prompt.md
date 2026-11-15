---
description: >-
  ADR-0137's flip. EVAL-1 (feature customer-listing) adds a SQLite customers
  table; the feature's living physical schema under
  docs/architecture/lld/customer-listing/data/ was approved (v1) before the
  code, and /acs:code built exactly that table, left uncommitted on main. The
  customer-listing gap analyst should find every element matching, so after a
  passing drift review docs-sync moves the document approved -> implemented
  through acs.py design status (by acs, with the reason), version unchanged,
  and records it in states.implemented.
expected_outcome: >-
  physical-schema.md front matter reads status implemented, version 1,
  status_by acs, a status_at instant and a status_reason saying the code
  matches; the docs-sync state lists it under implemented; nothing committed
  and no branch created or switched; no questions.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2700
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:docs-sync skill for ticket EVAL-1. The code change is done and
left uncommitted in the working tree on main; bring whatever docs it requires
in line with it, including the feature's design documents. Leave your doc
changes uncommitted too -- do not create a branch, commit, push or open a PR.
I am not available to answer questions: do not ask me anything, make any call
you need to and note it in your report.
