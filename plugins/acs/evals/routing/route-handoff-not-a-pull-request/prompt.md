---
description: >-
  Borrows the vocabulary of /acs:create-pr on purpose -- it talks about pull
  requests and committing to a branch -- while the request still belongs to
  this skill. It tests that the description, not a keyword, decides the
  route. Never names the skill.
expected_outcome: Routes to acs:handoff.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't open a pull request and don't commit anything to a branch. Just get my unfinished work on SHOP-12 over to Minh so he can finish it on his machine.
