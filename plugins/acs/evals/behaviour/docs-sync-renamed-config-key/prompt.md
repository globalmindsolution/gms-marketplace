---
description: >-
  A ticket whose change renames the page-size environment variable
  (SHOP_PAGE_SIZE -> SHOP_CUSTOMERS_PAGE_SIZE), uncommitted on main as
  /acs:code leaves it (ADR-0127), with /acs:code recorded completed and no doc
  updated. The old name is documented in two places, README.md and
  docs/configuration.md. docs-sync should fix both in the working tree and
  commit nothing.
expected_outcome: >-
  README.md and docs/configuration.md both document SHOP_CUSTOMERS_PAGE_SIZE
  as the setting and neither still lists SHOP_PAGE_SIZE as one; nothing
  committed and no branch created or switched (HEAD still main, its reflog
  unchanged); files names both docs; no questions.
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
