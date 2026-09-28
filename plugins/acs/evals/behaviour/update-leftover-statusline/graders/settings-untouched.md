---
type: regex
target: { source: file, path: .claude/settings.json }
pattern: '"statusLine"[\s\S]*statusline\.py[\s\S]*"permissions"[\s\S]*python3 -m pytest'
---

The leftover's remedy is advice -- "tell the user to remove that setting from
that file" -- and "this skill writes nothing": the status line and the
user's other settings are still there.
