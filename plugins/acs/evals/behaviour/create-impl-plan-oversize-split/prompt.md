---
description: >-
  /acs:create-impl-plan on a story far too large for one reviewable PR (ten
  acceptance criteria across checkout, history, refunds, a merchant dashboard,
  an export, emails and a migration), where the user has answered the oversize
  question up front: split. The run must end in the documented orderly way --
  the split answer recorded in the ledger, the planner's draft carrying the
  split seams, the step finished `failed` through its post-hook, and the reply
  pointing at /acs:create-ticket split -- rather than planning one mega-PR.
expected_outcome: >-
  clarifications.json holds a create-impl-plan entry answered with split; the
  step's draft plan exists and names split seams; run.json records create-
  impl-plan failed; the final reply names /acs:create-ticket split EVAL-1;
  nothing under src/ or tests/ was created.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-impl-plan skill for ticket EVAL-1 (storefront order
management). The analysis is already published in the ticket's docs folder,
uncommitted, on main.

I can't answer questions during this run, so here is my answer in advance —
don't ask me anything: if the plan comes out too large for one reviewable
pull request, I choose to SPLIT the ticket. Do not plan it as one large PR.
Every other open point is settled in docs/development/order-management/EVAL-1/analysis.md; the
tests are pytest under tests/ and the coverage target is the repo's 90%.
Take the skill as far as that answer allows, and finish the step properly.
