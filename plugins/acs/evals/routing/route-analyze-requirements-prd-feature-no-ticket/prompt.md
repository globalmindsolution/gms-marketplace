---
description: >-
  A natural-language request in the skill's domain, never naming the skill:
  a Discovery analysis of a PRD feature, with no ticket at all (ADR-0128).
expected_outcome: Routes to acs:analyze-requirements.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

There's no ticket for this yet — take the order tracking feature from our PRD and work out what it would really change in the code, what's still unclear about it, and what we'd be assuming.
