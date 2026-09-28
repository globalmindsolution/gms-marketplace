---
description: >-
  Borrows the vocabulary of /acs:code on purpose -- it is about the changes
  on a branch -- while the request still belongs to this skill. It tests
  that the description, not a keyword, decides the route. Never names the
  skill. On 2026-09-28 the prompt stopped saying only "examine what's on this
  branch and tell me what's wrong with it", which asks for no review at all:
  reading the diff yourself is an equally good answer to it, and the model
  looked for a shell to run git diff in 4 of 5 runs. It now asks for a
  review of the changes.
expected_outcome: Routes to acs:review-code.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't change anything. Give the changes on this branch a proper review against main and tell me what's wrong with them.
