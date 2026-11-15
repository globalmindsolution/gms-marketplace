---
description: >-
  A ticket whose change is an internal refactor (a private page-builder
  helper, behaviour unchanged), uncommitted on main as /acs:code leaves it
  (ADR-0127), with /acs:code recorded completed. No doc is stale. docs-sync
  should re-derive that from the changeset, change and commit nothing, finish
  completed with an empty files list, and say so.
expected_outcome: >-
  The docs-sync result completed with files []; nothing committed and no
  branch created or switched (HEAD still main, its reflog unchanged);
  README.md and CHANGELOG.md byte-for-byte unchanged; no doc file created; the
  reply says no doc needed updating; no questions.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:docs-sync skill for ticket EVAL-1. The code change is done and
left uncommitted in the working tree on main; bring whatever docs it made
stale in line with it. Leave any doc change uncommitted -- do not create a
branch, commit, push or open a PR. I am not available to answer questions: do
not ask me anything, make any call you need to and note it in your report.
