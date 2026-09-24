---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:run-e2e-tests.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-33's test cases name the checkout and payments suites. Run just those and report the results.
