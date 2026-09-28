---
type: regex
target: last_message
pattern: 'lock[^\n]{0,60}released|released[^\n]{0,60}lock'
flags: i
---

The release deletes `runs/EVAL-1/lock.json`, which no grader can see go (a
scaffold-made file), so it is graded as the report states it (Step 5).
