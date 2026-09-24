---
description: >-
  Borrows the vocabulary of /acs:create-pr on purpose -- it asks for a PR --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:release.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Open the version-bump PR for 2.0.0: the CHANGELOG section dated today and every version file bumped.
