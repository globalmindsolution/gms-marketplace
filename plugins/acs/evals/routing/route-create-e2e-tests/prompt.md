---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  The neighbours are create-test-docs and run-e2e-tests; the prompt
  presupposes the cases already exist and asks for the suites to be
  authored, not run.
expected_outcome: Routes to acs:create-e2e-tests.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-1's test plan has three end-to-end cases and none of them exist yet. Write those suites on the ticket branch.
