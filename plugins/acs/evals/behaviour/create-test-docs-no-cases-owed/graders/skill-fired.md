---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-test-docs"'
min: 1
---

The run must invoke `acs:create-test-docs`: its pre-hook is what settles the no-op.
