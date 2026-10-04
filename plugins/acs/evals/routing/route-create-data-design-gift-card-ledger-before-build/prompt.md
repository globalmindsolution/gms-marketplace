---
description: >-
  A natural-language request in the skill's domain, never naming the
  skill. The neighbour is create-impl-plan; the prompt is scoped to the
  data model the plan will later implement.
expected_outcome: Routes to acs:create-data-design.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-95 adds a gift-card balance ledger and is still in the Design phase. Before implementation, give me the ledger's entities and relationships, then its tables, keys, indexes and the migration steps in prose.
