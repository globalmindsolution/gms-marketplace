---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-design.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-71 is the epic for the new analytics ingestion pipeline, marked as needing a design. We can't agree on batch versus streaming, so work through both against our codebase and get one approach approved.
