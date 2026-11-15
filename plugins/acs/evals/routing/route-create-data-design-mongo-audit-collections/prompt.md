---
description: >-
  A natural-language request in the skill's domain, never naming the
  skill. The neighbour is create-api-contract; the prompt is scoped to
  what is stored, not what is exposed.
expected_outcome: Routes to acs:create-data-design.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-73 stores customer audit trails in MongoDB. Design the audit-trail feature's collections, their fields and indexes, and a migration outline, checked against what the code's models define today.
