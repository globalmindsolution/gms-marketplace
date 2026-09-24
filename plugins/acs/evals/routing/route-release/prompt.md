---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  The prompt used to end "open the release PR", naming the skill it should
  reach -- which grades the prompt, not the description. It was reworded
  when the no-self-naming rule, previously applied to three probes, was
  applied to all of them.
expected_outcome: Routes to acs:release.
tags: [routing, description]
max_turns: 10
allowed_tools: [Skill]
---

Cut version 0.4.10: assemble the changelog section and open the version-bump PR.
