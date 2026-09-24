---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:merge-pr.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

Priya approved PR #301 for TKT-58 and it no longer conflicts with main. Finish it off: merge it and remove the leftover branches.
