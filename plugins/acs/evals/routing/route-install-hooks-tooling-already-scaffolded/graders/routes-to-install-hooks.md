---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?install-hooks"'
min: 1
---

Passes when `acs:install-hooks` is invoked at least once, bare or plugin-qualified.
It reads the Skill tool call, not the reply, so a precondition gate
refusing AFTER the skill routed still counts as a route.
