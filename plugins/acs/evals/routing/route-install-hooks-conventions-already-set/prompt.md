---
description: >-
  Borrows the vocabulary of /acs:setup on purpose -- it talks about the
  conventions -- while the request still belongs to this skill. It tests
  that the description, not a keyword, decides the route. Never names the
  skill.
expected_outcome: Routes to acs:install-hooks.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The conventions are already configured and I don't want to change them. I only need the local commit-msg and pre-push checks put in place in this clone.
