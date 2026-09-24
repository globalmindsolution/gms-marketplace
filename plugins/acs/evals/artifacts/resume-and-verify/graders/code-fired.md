---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?code"'
min: 1
---

`acs:code` must be invoked. Without this, a session that edited app.py by hand
would pass the file grader below.
