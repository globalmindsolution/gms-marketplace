---
description: >-
  Borrows the vocabulary of /acs:review-code on purpose -- it talks about
  someone else's changes on a ticket -- while the request still belongs to
  this skill. It tests that the description, not a keyword, decides the
  route. Never names the skill.
expected_outcome: Routes to acs:handoff.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't review anything yet. Minh sent me his in-progress changes on SHOP-15 through git this morning: restore them here along with his note, then tell me what to run next.
