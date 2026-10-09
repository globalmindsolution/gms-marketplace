---
description: >-
  /acs:create-ticket in a repo that has no PRD. Tickets are made from the PRD
  and link it (ADR-0144), so the skill's pre-gate refuses before any ticket id
  is minted, and the reply tells the user to write the PRD first with
  /acs:create-prd -- it never writes a ticket by hand around the refusal.
expected_outcome: >-
  The Skill tool is called for create-ticket; no ticket partition (EVAL-1) is
  created and no ticket.json exists anywhere; the final reply names
  /acs:create-prd as the next step.
tags: [behaviour]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-ticket skill with this request:

Add a wishlist: a shopper can save a product to a wishlist and come back to it
later from any device.

I can't answer questions during this run, so don't ask me anything.
