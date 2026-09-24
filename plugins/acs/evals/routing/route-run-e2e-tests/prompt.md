---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  The neighbour is create-e2e-tests, and the alias `test` shares the domain;
  the prompt asks for execution and results, never for authoring.
expected_outcome: Routes to acs:run-e2e-tests.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

Execute the end-to-end suites for TKT-1 and tell me which of its cases passed.
