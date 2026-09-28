---
description: >-
  A ticket branch whose committed code change (PAGE_SIZE 20 -> 50) left
  README.md stale ("20 per page by default"), with /acs:code recorded
  completed. docs-sync should bring the README in line as a new commit on the
  same ticket branch, never a new branch or an amended commit.
expected_outcome: >-
  README.md says 50 per page and no longer 20; the ticket branch gained a new
  EVAL-1 commit after the code commit; HEAD is still the ticket branch; the
  docs-sync result lists README.md in docs_committed; no questions.
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
