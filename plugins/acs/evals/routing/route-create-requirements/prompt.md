---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  It was a known confound while the prompt only presupposed an existing
  codebase: on an empty repo the model looked, found nothing, and asked
  instead of routing. The prompt now describes the codebase itself, and a
  routing run is one turn with only the Skill tool, so there is nothing to
  look at and no turn in which to find it missing. Re-measured by the next
  paid run; until then its history is a caveat, not a baseline.
expected_outcome: Routes to acs:create-requirements.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

This repository is an existing codebase — a Node.js API with about sixty route handlers and no written requirements. Reverse-engineer its functional and non-functional requirements from the source.
