---
type: tool_used
arm: both
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?code-trivial"'
min: 0
max: 0
---

`acs:code-trivial` must not fire. `input_match` narrows the count to that one
skill, so routing to a DIFFERENT skill passes. Both bounds are set on
purpose: `min` defaults to 1, and `max: 0` alone would assert 1..0.
