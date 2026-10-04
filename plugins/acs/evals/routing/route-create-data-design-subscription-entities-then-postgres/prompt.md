---
description: >-
  A natural-language request in the skill's domain, never naming the
  skill. The neighbour is create-architecture; the prompt is scoped to one
  feature's attributes and keys and their Postgres mapping.
expected_outcome: Routes to acs:create-data-design.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

Our solution architect wants TKT-67's subscription-billing entities laid out properly: attributes, primary and foreign keys and cardinalities, database-agnostic first, then how that maps onto Postgres tables.
