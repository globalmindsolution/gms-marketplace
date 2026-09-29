---
description: >-
  Borrows the vocabulary of /acs:analyze-requirements on purpose -- it
  talks about a ticket's requirements -- while the request still belongs
  to this skill. It tests that the description, not a keyword, decides the
  route. Never names the skill.
expected_outcome: Routes to acs:create-requirements.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

I'm not asking about any single ticket's requirements. I want the repo-wide requirements doc set for this Flask inventory service, reverse-engineered from the code, one file per feature.
