---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:setup.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

I want every pull request in this repo to be blocked from merging unless its description names a ticket. Install that check for the acs workflow.
