---
type: regex
target: last_message
pattern: 'git\s*ignor|ignore rule|\.gitignore'
flags: i
---

The reply surfaces the swallowed-files warning; a run that stayed silent
leaves the user with a check that fails on every PR for a reason they never
heard.
