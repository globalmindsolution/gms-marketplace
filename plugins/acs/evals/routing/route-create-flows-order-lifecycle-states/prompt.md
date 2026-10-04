---
description: >-
  A natural-language request in the skill's domain, never naming the
  skill. The neighbour is create-data-design; the prompt is scoped to
  lifecycle states and the messages that move them, not tables.
expected_outcome: Routes to acs:create-flows.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

For TKT-46 we need the order entity's lifecycle pinned down: every state from placed to delivered or cancelled, which message triggers each transition, plus the checkout and cancel sequence diagrams.
