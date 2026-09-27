---
description: >-
  Borrows the vocabulary of /acs:review-code on purpose -- it opens on a
  clean code review -- while the request still belongs to this skill. It
  tests that the description, not a keyword, decides the route. Never
  names the skill.
expected_outcome: Routes to acs:create-pr.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The code review on TKT-77 came back clean with no blocking findings. Next step is getting a pull request up for the humans to look at.
