---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-api-contract.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

The plan for TKT-69 switches /customers from offset to cursor pagination. Document the new query parameters and response envelope, the errors, and how existing clients stay compatible.
