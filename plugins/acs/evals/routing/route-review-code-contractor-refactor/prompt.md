---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:review-code.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

A contractor pushed a big refactor of the billing module to their branch. Scrutinize it against origin/main for correctness and security problems; leave the code untouched and just report findings.
