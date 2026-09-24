---
description: >-
  Borrows the vocabulary of /acs:create-ticket on purpose -- it talks
  about creating tickets and a backlog -- while the request still belongs
  to this skill. It tests that the description, not a keyword, decides the
  route. Never names the skill.
expected_outcome: Routes to acs:create-prd.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't create any tickets yet. Before there's a backlog, write down what this telehealth product is, the problem it solves, its target users and the metrics that will tell us it worked.
