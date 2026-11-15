---
description: >-
  EVAL-1's code change (PAGE_SIZE 20 -> 50) was committed on a ticket branch
  by an older acs, but the checkout is on main, whose working tree carries no
  change. docs-sync has no branch precondition (ADR-0127): it reads the run's
  changeset with acs.py changes diff, finds it empty, and finishes with no doc
  owed -- neither switching branches nor editing or committing anything.
expected_outcome: >-
  HEAD still on main; neither main nor the ticket branch gained a commit;
  README.md unchanged; the docs-sync result finished completed with an empty
  files list; the reply says there was no changeset to sync; no questions.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:docs-sync skill for ticket EVAL-1: bring whatever docs its code
change made stale in line with it. Do not push or open a PR. I am not
available to answer questions: do not ask me anything, make any call you need
to and note it in your report.
