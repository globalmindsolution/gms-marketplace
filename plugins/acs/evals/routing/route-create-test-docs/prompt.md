---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  The neighbours are create-e2e-tests and run-e2e-tests; the prompt asks for
  the cases to be derived and written down, never for suites to be authored
  or run.
expected_outcome: Routes to acs:create-test-docs.
tags: [routing, description]
max_turns: 10
allowed_tools: [Skill]
---

Work out the test cases TKT-1 needs from its acceptance criteria, and say which suite each one belongs in.
