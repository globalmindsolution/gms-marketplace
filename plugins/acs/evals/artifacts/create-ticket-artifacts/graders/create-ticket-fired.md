---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-ticket"'
min: 1
---

The `acs:create-ticket` skill must be invoked. Free and deterministic: without
this, a run that hand-wrote a plausible ticket.json would grade as a pass.
