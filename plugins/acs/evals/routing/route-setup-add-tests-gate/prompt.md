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

Add the CI gate that runs our test suite and fails a PR when coverage drops below the target, for the acs pipeline in this repo.
