---
description: >-
  Borrows the vocabulary of /acs:review-code on purpose -- it talks about reviewing the code --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:docs-sync.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

I'm not asking for a code review of TKT-52, the code is fine. Its diff changed the cache TTL from 5 to 15 minutes and the README's caching section still says 5; make the docs agree with the branch.
