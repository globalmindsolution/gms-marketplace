---
description: >-
  Borrows the vocabulary of /acs:code on purpose -- it asks about the
  migration and implementation -- while the request still belongs to this
  skill. It tests that the description, not a keyword, decides the route.
  Never names the skill.
expected_outcome: Routes to acs:create-data-design.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't write the migration for TKT-77 yet. First document the bookings feature's schema change: the logical entities, the physical tables and indexes, and an ordered migration outline with its rollback, as design documents only.
