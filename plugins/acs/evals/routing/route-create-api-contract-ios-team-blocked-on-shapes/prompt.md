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

The iOS team is blocked on us: TKT-55's plan adds a /v2/wallet/balance endpoint and they need the exact JSON shapes, status codes and a sample response before they start.
