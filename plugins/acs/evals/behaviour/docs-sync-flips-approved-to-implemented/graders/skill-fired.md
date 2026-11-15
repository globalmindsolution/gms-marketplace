---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?docs-sync"'
min: 1
---

`acs:docs-sync` must be invoked: since ADR-0137 it is the skill that moves a
feature's LLD document to `implemented` once the code matches it.
