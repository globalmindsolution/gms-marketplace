---
description: >-
  EVAL-1's code change (PAGE_SIZE 20 -> 50) is committed on its ticket branch
  and /acs:code recorded that branch, but the checkout is on main. docs-sync's
  branch confirmation is a hard precondition: it should fail fast, surface the
  mismatch, and neither switch branches nor commit anything.
expected_outcome: >-
  HEAD still on main; neither main nor the ticket branch gained a commit; the
  docs-sync result finished failed; the reply names the branch mismatch; no
  questions.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:docs-sync skill for ticket EVAL-1: bring whatever docs its code
change made stale in line with it. Do not push or open a PR. I am not
available to answer questions: do not ask me anything, make any call you need
to and note it in your report.
