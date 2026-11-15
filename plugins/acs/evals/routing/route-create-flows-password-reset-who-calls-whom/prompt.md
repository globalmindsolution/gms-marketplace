---
description: >-
  A natural-language request in the skill's domain, never naming the
  skill. The neighbour is create-api-contract; the prompt is scoped to the
  order of calls between participants, not request and response shapes.
expected_outcome: Routes to acs:create-flows.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-63 is in the Design phase and its runtime behaviour needs designing before implementation: who calls whom, in what order, for a password reset, and the reset token's lifecycle as a state diagram.
