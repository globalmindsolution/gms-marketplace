---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-project"'
min: 1
---

The create-project leg really ran as its own Skill call -- dispatched by
/acs:project in bootstrap mode, so its own pre-hook and gate fired.
