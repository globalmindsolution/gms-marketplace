---
description: >-
  A natural-language request in the skill's domain, never naming the skill:
  the requirements arrive as an attached document, not a ticket (ADR-0128).
expected_outcome: Routes to acs:analyze-requirements.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

Product sent over a spec for bulk customer export (~/Downloads/bulk-export-spec.pdf). Go through it against our codebase: what it touches, what it leaves open, and the acceptance criteria it should really have before anyone plans the work.
