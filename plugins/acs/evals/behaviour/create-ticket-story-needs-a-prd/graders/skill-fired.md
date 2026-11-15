---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-ticket"'
min: 1
---

The request names /acs:create-ticket, so the skill is what refuses -- not a
session that decided on its own not to run it.
