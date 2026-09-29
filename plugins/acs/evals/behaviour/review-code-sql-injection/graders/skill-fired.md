---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?review-code"'
min: 1
---

`acs:review-code` must be invoked. Without this, a session that read the diff
and wrote its own review would pass the file graders below.
