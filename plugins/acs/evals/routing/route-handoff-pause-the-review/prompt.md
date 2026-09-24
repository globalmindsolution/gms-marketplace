---
description: >-
  Borrows the vocabulary of /acs:review-code on purpose -- it talks about the review in progress --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:handoff.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Skip the rest of the review for now, I'll come back to it. Mark this step interrupted, release the lock, and tell me how to resume the run in a fresh session.
