---
description: >-
  A ticket with a tech design whose change -- uncommitted on main, as /acs:code
  leaves it (ADR-0127) -- moves customers onto a SQLite store, with an
  approved design in the ticket's docs folder recording one accepted decision
  under "Decision records", a repo that keeps ADRs in docs/adr/ (0001, 0002),
  and /acs:code recorded completed with no doc updated. docs-sync should
  write that decision as the next ADR in the working tree, commit nothing,
  and leave the existing ADRs untouched.
expected_outcome: >-
  A new docs/adr/0003-*.md, uncommitted; files names it; ADR 0002 unchanged;
  nothing committed and no branch created or switched (HEAD still main, its
  reflog unchanged); no questions.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2700
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:docs-sync skill for ticket EVAL-1. The code change is done and
left uncommitted in the working tree on main; bring whatever docs it requires
in line with it. Leave your doc changes uncommitted too -- do not create a
branch, commit, push or open a PR. I am not available to answer questions: do
not ask me anything, make any call you need to and note it in your report.
