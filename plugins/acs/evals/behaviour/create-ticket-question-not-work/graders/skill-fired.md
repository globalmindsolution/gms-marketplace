---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-ticket"'
min: 0
max: 0
arm: both
---

A question about an existing ticket is not new work: `acs:create-ticket` must not be invoked, whose mandatory first action mints an id.
