---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-impl-plan.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

The analysis on TKT-66 — moving the mobile app's offline cache to SQLite — is complete and signed off. Work out the step-by-step approach, which modules each executor owns, and what gets tested, so we can judge the delivery path.
