---
description: >-
  Borrows the vocabulary of /acs:merge-pr on purpose -- it says "merge" --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:create-pr.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't merge anything. Just open the pull request for TKT-15's branch so reviewers can start.
