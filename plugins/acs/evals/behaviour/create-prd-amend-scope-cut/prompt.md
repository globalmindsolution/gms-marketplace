---
description: >-
  /acs:create-prd amend mode after a scope change: leadership cut order
  tracking, which the existing PRD lists as a Should-have with its own v2.6.0
  milestone. It should mint an "Amend PRD:" delivery ticket, move order
  tracking to Won't and Out of scope, drop its milestone and release row from
  the roadmap, leave every other section byte-for-byte, push the delivery
  branch, and report the failed gh PR step as a finding.
expected_outcome: >-
  EVAL-1 titled "Amend PRD: ..."; docs/product/prd.md lists order tracking
  under Won't and Out of scope, with Vision through Goals and the NFR and
  Constraints sections unchanged; docs/product/roadmap.md keeps Checkout
  v2.5.0 and no longer mentions v2.6.0; a task/EVAL-1-* branch pushed with
  upstream set; result.json records the gh failure and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-prd skill with the argument `cut order tracking from
scope` to amend our PRD. Leadership cut order tracking this week. I have
already decided exactly what changes; treat all of it as confirmed and do not
ask me anything:

- Features (prioritized): order tracking moves from Should to Won't.
- Out of scope: add order tracking.
- Roadmap: remove the "Order tracking — v2.6.0" milestone and its v2.6.0 row
  from the Release versions table. Checkout stays in v2.5.0.
- Nothing else changes: every other section of the PRD and the rest of the
  roadmap stay exactly as they are, word for word.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
