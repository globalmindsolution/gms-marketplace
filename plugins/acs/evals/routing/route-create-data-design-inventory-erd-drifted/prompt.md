---
description: >-
  A natural-language request in the skill's domain, never naming the
  skill. The neighbour is docs-sync; the prompt is scoped to the feature's
  data low-level design in the Design phase, not reconciling docs after a
  change.
expected_outcome: Routes to acs:create-data-design.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

The low-level data docs for the inventory feature are stale against the models in the code. As part of TKT-88, revise inventory's ERD and table-level schema so they match what is built plus what the ticket adds.
