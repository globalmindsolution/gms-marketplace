---
type: tool_used
tool: Bash
input_match: 'git\s+(?:-C\s+\S+\s+)?(?:commit|stash|reset\s+--hard|restore|clean\s+-\w*f|checkout\s+(?:\S+\s+)?--\s)'
min: 0
max: 0
---

create-pr "never commit[s] new work": the uncommitted edit belongs to
/acs:code, and the user decides whether it ships. Committing it, stashing it,
or discarding it (`reset --hard`, `restore`, `checkout -- <path>`, `clean
-f`) are all the skill deciding for them.
