---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:review-code.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

I just finished implementing TKT-63's rate limiter. Before anyone else sees it, go over the changes with a fine-tooth comb and gate it on build, lint, unit tests and coverage.
