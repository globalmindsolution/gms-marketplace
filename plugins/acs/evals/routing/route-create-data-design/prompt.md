---
description: >-
  A natural-language request in the skill's domain, never naming the
  skill. The neighbour is create-architecture; the prompt is scoped to one
  ticket's feature-level entities, keys and tables rather than the
  product-wide conceptual model.
expected_outcome: Routes to acs:create-data-design.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-31 adds wishlists. Before anyone builds it, lay out the feature's entities, keys and cardinalities as a logical ERD, and the physical tables, indexes and migration outline that go with it.
