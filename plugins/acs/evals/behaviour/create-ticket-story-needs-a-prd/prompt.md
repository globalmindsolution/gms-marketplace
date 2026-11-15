---
description: >-
  /acs:create-ticket asked for user-facing work (a wishlist) in a repo that has
  no PRD. Product work is made from the PRD and links it (ADR-0144), so the run
  ends failed instead of completing a story, and the reply tells the user to
  write the PRD first with /acs:create-prd -- it never relabels the work a task
  to get past the rule, nor writes a ticket by hand.
expected_outcome: >-
  The Skill tool is called for create-ticket; its step state records the run
  failed, never completed; the final reply names /acs:create-prd as the next
  step.
tags: [behaviour]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-ticket skill with this request:

Add a wishlist: a shopper can save a product to a wishlist and come back to it
later from any device.

I can't answer questions during this run, so don't ask me anything.
