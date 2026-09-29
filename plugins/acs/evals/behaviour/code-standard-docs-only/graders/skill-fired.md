---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?code-standard"'
min: 1
---

The leg, not the entry point. The plan's `## Contract` block records
`standard` (approved by the scaffold through `acs.py plan check`), and
/acs:code dispatches to `acs:code-standard` with a real Skill call.
