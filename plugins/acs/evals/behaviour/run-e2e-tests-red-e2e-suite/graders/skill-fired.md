---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?run-e2e-tests"'
min: 1
---

`acs:run-e2e-tests` must be invoked. Without it, a session that ran the two
commands itself and reported the failure would pass the reply grader.
