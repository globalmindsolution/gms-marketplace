---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-architecture.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

New hires keep asking how our data pipeline hangs together, and the diagrams are two years stale. Rebuild the HLD and LLD docs from the current repo as a docs-only PR.
