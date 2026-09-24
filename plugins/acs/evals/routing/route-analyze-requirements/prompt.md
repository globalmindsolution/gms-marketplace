---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  Deliberately pre-plan: the neighbour is create-impl-plan, so the prompt
  asks for understanding and open questions, never for an approach or a file
  list.
expected_outcome: Routes to acs:analyze-requirements.
tags: [routing, description]
max_turns: 10
allowed_tools: [Skill]
---

Before we plan anything for TKT-1, work out what it really asks for: what breaks, what is unclear, and what we are assuming.
