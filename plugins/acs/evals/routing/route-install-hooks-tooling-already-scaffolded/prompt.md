---
description: >-
  Borrows the vocabulary of /acs:project on purpose -- it talks about the repo's tooling and pre-commit config --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:install-hooks.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

This repo already has its tooling and pre-commit config, so don't scaffold anything. I just want the branch-name and commit-message checks active in my local git.
