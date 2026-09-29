---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:docs-sync.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

The coder's summary for TKT-17 says no docs needed changing, but the branch removed the /v1/export endpoint and the API reference still lists it. Verify against the diff itself and fix whatever is stale.
