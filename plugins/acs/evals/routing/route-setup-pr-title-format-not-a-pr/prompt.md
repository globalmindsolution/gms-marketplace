---
description: >-
  Borrows the vocabulary of /acs:create-pr on purpose -- it is about pull
  request titles -- while the request still belongs to this skill. It
  tests that the description, not a keyword, decides the route. Never
  names the skill.
expected_outcome: Routes to acs:setup.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

I'm not opening a pull request. I want to change the PR title format acs uses so every title starts with the ticket id in brackets.
