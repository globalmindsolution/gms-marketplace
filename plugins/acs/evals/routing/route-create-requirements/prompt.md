---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  KNOWN CONFOUND: the prompt presupposes an existing codebase to reverse-
  engineer, and the case runs in an empty workspace. That is measured, not
  hypothetical: on an empty repo the model looked, found nothing, and asked
  instead of routing. `allowed_tools: [Skill]` removes the looking, not the
  absence -- seed a codebase before reading a miss here as a description
  defect.
expected_outcome: Routes to acs:create-requirements.
tags: [routing, description]
max_turns: 10
allowed_tools: [Skill]
---

Reverse-engineer the functional and non-functional requirements out of this existing codebase.
