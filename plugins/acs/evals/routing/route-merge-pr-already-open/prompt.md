---
description: >-
  Borrows the vocabulary of /acs:create-pr on purpose -- it talks about
  opening a pull request -- while the request still belongs to this skill.
  It tests that the description, not a keyword, decides the route. Never
  names the skill.
expected_outcome: Routes to acs:merge-pr.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The pull request is already open and approved, so don't open another one. Merge it with our usual strategy and close out the ticket.
