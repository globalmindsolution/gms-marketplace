---
description: >-
  Borrows the vocabulary of /acs:docs-sync on purpose -- docs that no longer
  match the code -- while the request still belongs to this skill: it is
  product-wide, about the architecture set, and asks for a report with no
  edit or commit. It tests that the description, not a keyword, decides the
  route. Never names the skill.
expected_outcome: Routes to acs:audit-design.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

This is not about one ticket's changeset or its README. Across the whole product, which parts of the architecture set no longer agree with the code? Report only -- don't edit or commit any document.
