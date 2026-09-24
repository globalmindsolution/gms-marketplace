---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:update.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

I'm on acs 0.4.2. Summarize the changelog between my installed plugin and the newest one, then bring me up to date.
