---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?setup"'
min: 0
max: 0
arm: both
---

`acs:setup` must not fire for a request that is not about acs. `arm: both`
scores it in both arms; both bounds are needed because `min` defaults to 1.
