---
description: >-
  Borrows the vocabulary of /acs:create-pr on purpose -- it mentions opening
  the pull request -- while the request still belongs to this skill. It
  tests that the description, not a keyword, decides the route. Never names
  the skill.
expected_outcome: Routes to acs:code.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't open the pull request for TKT-95 yet; the approved plan hasn't been built. Implement it test-first on the ticket branch so there is something to put up for review.
