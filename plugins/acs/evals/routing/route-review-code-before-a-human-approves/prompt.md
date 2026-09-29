---
description: >-
  Borrows the vocabulary of /acs:merge-pr on purpose -- it is about a PR's
  approvals and readiness -- while the request still belongs to this
  skill. It tests that the description, not a keyword, decides the route.
  Never names the skill.
expected_outcome: Routes to acs:review-code.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Nobody has approved TKT-81's PR yet and I'm not asking you to merge it. Before a human reviewer spends time on it, go through the code changes yourself and flag anything blocking.
