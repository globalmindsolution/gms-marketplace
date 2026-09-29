---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?docs-sync"'
min: 1
---

`acs:docs-sync` must be invoked. Without it, a direct edit to README.md would
pass the file graders -- and the skill's own description says a doc fix that
follows from a ticket's change goes through it.
