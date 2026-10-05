---
description: >-
  A natural-language request in the skill's domain, never naming the
  skill. The neighbour is create-tech-design; the prompt is scoped to
  diagramming a flow's business rules, not choosing an approach.
expected_outcome: Routes to acs:create-flows.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-52's refund flow branches on business rules: partial versus full, and inside or past the 30-day window. Document it as a sequence diagram with an activity diagram for the decision logic, in the refunds feature's low-level design.
