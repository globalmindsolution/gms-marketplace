---
description: >-
  Borrows the vocabulary of /acs:create-architecture on purpose -- it
  opens on the architecture docs -- while the request still belongs to
  this skill. It tests that the description, not a keyword, decides the
  route. Never names the skill.
expected_outcome: Routes to acs:create-requirements.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The architecture docs are already in place for this Java billing platform; what we lack are the functional and non-functional requirements. Derive them from the codebase with the architecture as context, one file per item.
