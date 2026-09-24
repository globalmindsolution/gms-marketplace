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

Implementation of TKT-63, the mobile push-notification opt-in, just landed on its branch. test-cases.md has TC-4 and TC-5 typed e2e and our Detox suite under e2e/ has nothing for them — get them written before anyone runs the suite.
