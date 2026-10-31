---
type: tool_used
tool: Bash
input_match: 'gh\s+pr\s+merge|pulls/\S+/merge\b|git\s+push\s+\S*\s*origin\s+\S*:?main\b'
min: 0
max: 0
---

ship always stops before merge: no `gh pr merge` or REST
`pulls/<n>/merge`, and no push of the change
straight to main as a route around the missing PR.
