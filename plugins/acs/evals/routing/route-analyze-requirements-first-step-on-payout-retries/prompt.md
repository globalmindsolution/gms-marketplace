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

I have just picked up TKT-67, a story about retrying failed payouts in the settlement job. First thing: figure out what it really affects and what risks we are walking into, before we decide how to build it.
