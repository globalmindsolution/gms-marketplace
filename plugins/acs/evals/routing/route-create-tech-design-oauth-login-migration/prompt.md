---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-tech-design.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-64 moves login from session cookies to OAuth tokens, and I want the team to agree on how before anyone builds it. Before any implementation is specified, study the current auth flow, set out the options and write up the design for approval.
