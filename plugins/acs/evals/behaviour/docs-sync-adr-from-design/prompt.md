---
description: >-
  A needs_design ticket whose committed change moves customers onto a SQLite
  store, with an approved design on the branch recording one accepted
  decision under "Decision records", a repo that keeps ADRs in docs/adr/
  (0001, 0002), and /acs:code recorded completed with no doc updated.
  docs-sync should commit that decision as the next ADR on the same ticket
  branch, leaving the existing ADRs untouched.
expected_outcome: >-
  A new docs/adr/0003-*.md committed as a new EVAL-1 commit on
  task/EVAL-1-store-customers-in-sqlite; docs_committed names it; ADR 0002
  unchanged; HEAD still the ticket branch; no questions.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2700
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:docs-sync skill for ticket EVAL-1. The code change is done and
committed on the ticket branch, which is checked out; bring whatever docs it
requires in line with it. Commit on this branch and do not push or open a PR.
I am not available to answer questions: do not ask me anything, make any call
you need to and note it in your report.
