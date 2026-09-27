---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-e2e-tests.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-71's refund flow is coded and the verifier is green. Its test cases mark the full refund-through-the-Stripe-sandbox journey as e2e, and our Cypress folder has no spec for it yet — add those specs on the branch.
