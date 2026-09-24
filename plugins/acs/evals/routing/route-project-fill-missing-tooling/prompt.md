---
description: >-
  Borrows the vocabulary of /acs:setup on purpose -- it mentions acs
  conventions and CI -- while the request still belongs to this skill. It
  tests that the description, not a keyword, decides the route. Never names
  the skill.
expected_outcome: Routes to acs:project.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

This existing repo has no pre-commit, no coverage reporting and no CI workflow. Audit it against our standards and add only what is missing — leave the acs conventions as they are.
