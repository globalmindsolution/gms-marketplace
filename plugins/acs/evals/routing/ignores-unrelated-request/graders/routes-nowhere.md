---
type: tool_used
arm: both
tool: Skill
min: 0
max: 0
---

No skill may fire for a request with nothing to do with software
delivery. Without `input_match` this counts EVERY Skill call, so a
plugin whose descriptions over-trigger fails here. `arm: both`
scores it against the no-plugin baseline too, where it is a real
assertion rather than a structural zero.
