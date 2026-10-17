---
description: >-
  /acs:set-doc-status marking feature PRDs implemented, which is derived from
  their tickets (ADR-0146): card checkout's requirement is delivered (its
  story EVAL-1 merged), order tracking's is not (EVAL-2 still open). It
  should move card checkout's PRD to implemented, leave order tracking's
  approved -- never forcing it with --override-delivery, which the user gave
  no reason for -- and report order-tracking/R1 as still open.
expected_outcome: >-
  docs/product/features/card-checkout/prd.md is implemented at version 1;
  docs/product/features/order-tracking/prd.md is still approved at version 1
  with no status_reason; nothing committed or pushed; the reply says order
  tracking waits on order-tracking/R1.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, AskUserQuestion]
---

Run the /acs:set-doc-status skill with the arguments `implemented
card-checkout order-tracking`. I think both features are built now; mark
their PRDs implemented. Do not ask me anything, and don't commit anything.
