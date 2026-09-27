---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:setup.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

I want our branch names to follow feature/<ticket>-<slug> instead of acs's default. Change the convention.
