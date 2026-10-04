---
description: >-
  Borrows the vocabulary of /acs:review-code on purpose -- it asks for a
  review and a list of findings, the words a changeset review uses -- while
  the request still belongs to this skill: the design is compared with the
  code and the gaps reported, nothing edited. It tests that the description,
  not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:audit-design.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Not a review of a branch or a diff. I want the system design itself checked: compare our C4 views and integration map with the services and endpoints that actually exist, and classify every mismatch.
