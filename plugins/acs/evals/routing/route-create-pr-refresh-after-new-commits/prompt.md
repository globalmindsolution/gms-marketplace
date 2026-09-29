---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-pr.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

I opened the PR for TKT-58 yesterday, but I've since pushed two more commits for the currency-rounding fix. Refresh the pull request's title and description from the current ticket state.
