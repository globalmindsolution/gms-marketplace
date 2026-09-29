---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:analyze-requirements.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-73 says "notify users when their order ships" but never says push, email or SMS. Before planning, pin down the problem, log those unknowns as questions for the PM, and propose sharper acceptance criteria.
