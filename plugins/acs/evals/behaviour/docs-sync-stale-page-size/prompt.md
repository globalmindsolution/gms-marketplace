---
description: >-
  A ticket whose code change (PAGE_SIZE 20 -> 50) is uncommitted on main, as
  /acs:code leaves it (ADR-0127), left README.md stale ("20 per page by
  default"), with /acs:code recorded completed. docs-sync should bring the
  README in line in the working tree -- no branch, no commit (/acs:create-pr
  commits later).
expected_outcome: >-
  README.md says 50 per page and no longer 20; nothing committed and no
  branch created or switched (HEAD still main, its reflog unchanged); the
  docs-sync result lists README.md in files; no questions.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:docs-sync skill for ticket EVAL-1. The code change is done and
left uncommitted in the working tree on main; bring whatever docs it made
stale in line with it. Leave your doc changes uncommitted too -- do not create
a branch, commit, push or open a PR. I am not available to answer questions:
do not ask me anything, make any call you need to and note it in your report.
