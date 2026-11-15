---
type: tool_used
tool: Bash
input_match: 'git\s+(?:-C\s+\S+\s+)?(?:add|commit|stash|reset|restore|clean|checkout\s+(?:\S+\s+)?--\s)\b'
min: 0
max: 0
---

create-pr commits "ONLY through `acs.py pr commit --plan`": never `git add -A`,
`git add .`, `git commit -a` or any raw `git add` / `git commit`, and never
stash, reset, restore, clean or check out over the user's work. The CLI's own
git calls run inside it, not as Bash calls, so they do not count here.
