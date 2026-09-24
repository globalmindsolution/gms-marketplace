---
description: >-
  Borrows the vocabulary of /acs:review-code on purpose -- it talks about reviewing code --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:merge-pr.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The code review on TKT-66's PR is finished and approved, so I don't need another review pass. Check the branch protections and merge it.
