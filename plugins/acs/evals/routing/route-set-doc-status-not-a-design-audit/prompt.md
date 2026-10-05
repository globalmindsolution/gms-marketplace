---
description: >-
  Borrows the vocabulary of /acs:audit-design on purpose -- design
  documents, status and version, the code -- while the request still
  belongs to this skill: it rules out checking the docs against the code
  and asks only for the status to change. It tests that the description,
  not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:set-doc-status.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

I'm not asking whether the design docs match the code -- I already know the order-tracking LLD was built exactly as designed. Just change the status of those documents to implemented.
