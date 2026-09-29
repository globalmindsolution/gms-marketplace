---
description: >-
  A ticket branch whose committed change renames the page-size environment
  variable (SHOP_PAGE_SIZE -> SHOP_CUSTOMERS_PAGE_SIZE), with /acs:code
  recorded completed and no doc updated. The old name is documented in two
  places, README.md and docs/configuration.md. docs-sync should fix both and
  commit them on the same ticket branch.
expected_outcome: >-
  README.md and docs/configuration.md both document SHOP_CUSTOMERS_PAGE_SIZE
  as the setting and neither still lists SHOP_PAGE_SIZE as one; the ticket
  branch gained new EVAL-1 commit(s) after the code commit; HEAD still the
  ticket branch; docs_committed names both files; no questions.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:docs-sync skill for ticket EVAL-1. The code change is done and
committed on the ticket branch, which is checked out; bring whatever docs it
made stale in line with it. Commit on this branch and do not push or open a
PR. I am not available to answer questions: do not ask me anything, make any
call you need to and note it in your report.
