---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?run-e2e-tests"'
min: 1
---

`acs:run-e2e-tests` must be invoked: a session that looked at the settings
itself and replied "nothing configured" would pass the reply grader.
