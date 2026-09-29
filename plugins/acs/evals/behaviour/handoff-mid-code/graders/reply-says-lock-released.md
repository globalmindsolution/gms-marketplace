---
type: regex
target: last_message
pattern: 'lock[^\n]{0,60}released|released[^\n]{0,60}lock'
flags: i
---

The release deletes `runs/EVAL-1/lock.json`, and no grader can assert a
scaffold-made file is gone (`file_exists` sees only created paths; a regex on a
missing file fails). So the release is graded as the report states it, which
the skill's Step 5 requires.
