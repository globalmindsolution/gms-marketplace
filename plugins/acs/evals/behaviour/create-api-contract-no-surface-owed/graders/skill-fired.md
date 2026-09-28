---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-api-contract"'
min: 1
---

The run must invoke `acs:create-api-contract`: its pre-hook is what settles the no-op.
