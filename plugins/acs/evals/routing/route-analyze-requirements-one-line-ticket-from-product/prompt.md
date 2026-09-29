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

Product just handed us TKT-52: "let admins bulk-export invoices". Nobody has planned it yet, so restate the problem properly, flag the assumptions we are making, and say whether it touches the public API.
