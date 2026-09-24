---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?setup"'
min: 1
---

Display-only under ablation (a `tool_used: Skill` grader never moves the
score): shows whether `acs:setup` is what produced the result.
