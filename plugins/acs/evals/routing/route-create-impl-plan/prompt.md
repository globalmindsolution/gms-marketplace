---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  Deliberately post-analysis and pre-code: the neighbours are analyze-ticket
  and code, so the prompt asks for the approach, not for understanding or
  edits.
expected_outcome: Routes to acs:create-impl-plan.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-1 has been analysed and the questions are answered. Work out the file-by-file approach the implementation should follow.
