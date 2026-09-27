---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?standardize-project"'
min: 1
---

Passes when `acs:standardize-project` is invoked at least once, bare or plugin-qualified.
It reads the Skill tool call, not the reply, so a precondition gate
refusing AFTER the skill routed still counts as a route.

Explicit invocation: a typed `/acs:standardize-project` can be expanded by the CLI
before any model turn, in which case no Skill call happens and this
reads 0x for a probe that routed. Tagged `explicit` so it can be run
or left out deliberately.
