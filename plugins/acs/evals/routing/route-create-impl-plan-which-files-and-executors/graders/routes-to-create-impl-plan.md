---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-impl-plan"'
min: 1
---

Passes when `acs:create-impl-plan` is invoked at least once, bare or plugin-qualified.
It reads the Skill tool call, not the reply, so a precondition gate
refusing AFTER the skill routed still counts as a route.
