---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-tech-design"'
min: 1
---

The run must attempt `acs:create-tech-design` -- the refusal under test is the skill's own pre-hook, which fires on that Skill call.
