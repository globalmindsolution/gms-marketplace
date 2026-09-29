---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:merge-pr.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

The reviewer signed off on TKT-61's pull request an hour ago and the pipeline is green. Squash it in with our configured strategy and delete the branch and worktree.
