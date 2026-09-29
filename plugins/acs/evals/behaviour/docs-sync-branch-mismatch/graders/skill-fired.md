---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?docs-sync"'
min: 1
---

`acs:docs-sync` must be invoked: its branch confirmation is the behaviour
under test, and a session editing README.md directly would never meet it.
