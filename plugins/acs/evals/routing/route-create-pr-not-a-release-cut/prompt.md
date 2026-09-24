---
description: >-
  Borrows the vocabulary of /acs:release on purpose -- it talks about
  release cuts and version bumps -- while the request still belongs to
  this skill. It tests that the description, not a keyword, decides the
  route. Never names the skill.
expected_outcome: Routes to acs:create-pr.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

This isn't a release cut and there's no version bump. I just need the pull request for TKT-70's feature branch opened so reviewers can see it.
