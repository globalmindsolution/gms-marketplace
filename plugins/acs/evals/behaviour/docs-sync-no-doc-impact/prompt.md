---
description: >-
  A ticket branch whose committed change is an internal refactor (a private
  page-builder helper, behaviour unchanged), with /acs:code recorded
  completed. No doc is stale. docs-sync should re-derive that from the diff,
  change and commit nothing, finish completed with an empty docs_committed,
  and say so.
expected_outcome: >-
  The docs-sync result completed with docs_committed []; the ticket branch has
  no commit after the code commit; HEAD still the ticket branch; README.md and
  CHANGELOG.md byte-for-byte unchanged; no doc file created; the reply says no
  doc needed updating; no questions.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:docs-sync skill for ticket EVAL-1. The code change is done and
committed on the ticket branch, which is checked out; bring whatever docs it
made stale in line with it. Commit on this branch if anything needs
committing, and do not push or open a PR. I am not available to answer
questions: do not ask me anything, make any call you need to and note it in
your report.
