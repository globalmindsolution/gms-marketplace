---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?review-code"'
min: 1
---

`acs:review-code` must be invoked. Without this, a session that read the diff
and declared it fine would pass nothing else here, but it would not have been
the review under test.
