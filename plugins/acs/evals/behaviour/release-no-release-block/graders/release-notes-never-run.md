---
type: tool_used
tool: Bash
input_match: 'release_notes\.py'
min: 0
max: 0
---

The missing block is caught "immediately -- before invoking
`release_notes.py` at all": there is nothing meaningful to pass as
`--release-config`, so a `status`, `draft` or `bump` call means the run made
one up.
