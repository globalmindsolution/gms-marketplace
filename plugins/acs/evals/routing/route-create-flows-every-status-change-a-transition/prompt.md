---
description: >-
  A natural-language request in the skill's domain, never naming the
  skill. The neighbour is create-architecture; the prompt is scoped to one
  feature's interactions and one entity's transitions.
expected_outcome: Routes to acs:create-flows.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

Make sure every message in TKT-84's subscription-renewal interaction that changes the subscription's status shows up as a transition in its lifecycle diagram. Write the flow and state docs for that feature.
