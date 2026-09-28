---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?code"'
min: 1
---

`acs:code` must be invoked: the refusal under test is its PreToolUse gate's,
and that gate only fires on a real Skill call. A session that read the plan and
declined on its own would pass the outcome graders without exercising it.
