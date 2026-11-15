---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:audit-design.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

Somebody asked which parts of our documented architecture were never built. List everything the design docs describe that the code does not have, and anything the code has that they leave out.
