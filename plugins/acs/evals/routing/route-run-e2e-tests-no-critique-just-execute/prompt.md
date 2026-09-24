---
description: >-
  Borrows the vocabulary of /acs:review-code on purpose -- it mentions a
  critique and a verdict on the diff -- while the request still belongs to
  this skill. It tests that the description, not a keyword, decides the
  route. Never names the skill.
expected_outcome: Routes to acs:run-e2e-tests.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

I don't need a critique of the code or a verdict on the diff. Just execute every configured suite and tell me what fails.
