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

TKT-11 renamed the --out flag to --output and the change is committed on its branch, but the README and the CLI reference still show --out. Bring the docs in line with the diff.
