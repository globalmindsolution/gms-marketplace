---
description: >-
  A natural-language request in the skill's domain, never naming the
  skill. The neighbour is docs-sync; the prompt is scoped to the feature's
  behavioural design in the Design phase, not a doc reconciliation after a
  change.
expected_outcome: Routes to acs:create-flows.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

The payment-capture sequence and state diagrams for the payments feature no longer match the handlers. As part of TKT-71, update them against the code and note every gap you find.
