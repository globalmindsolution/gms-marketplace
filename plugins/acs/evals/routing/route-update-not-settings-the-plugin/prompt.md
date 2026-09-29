---
description: >-
  Borrows the vocabulary of /acs:setup on purpose -- it talks about acs
  settings -- while the request still belongs to this skill. It tests that
  the description, not a keyword, decides the route. Never names the
  skill.
expected_outcome: Routes to acs:update.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

I'm not changing any acs settings or conventions. I just want the acs plugin itself bumped to the latest version, with its settings-schema migration checks run afterwards.
