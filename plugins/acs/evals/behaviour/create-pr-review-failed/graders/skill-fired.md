---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-pr"'
min: 1
---

`acs:create-pr` must be invoked: the refusal below is the skill's pre-hook
answering that Skill call, not the model deciding on its own not to push.
