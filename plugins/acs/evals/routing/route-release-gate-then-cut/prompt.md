---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:release.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

Our pre-cut gate is configured in .acs/settings.json. Run it, and if it's green, cut 2.3.1 with the changelog and the version bumps.
