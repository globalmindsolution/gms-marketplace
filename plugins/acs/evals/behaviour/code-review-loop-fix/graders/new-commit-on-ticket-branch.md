---
type: regex
target: { source: file, path: .git/logs/refs/heads/task/EVAL-1-add-1-based-page-numbers-to-the-customer }
pattern: 'commit: EVAL-1 Page bounds for 1-based pages\n[\s\S]*\tcommit: '
---

The fix lands as a NEW commit on the SAME ticket branch. The branch's reflog
ends, after the scaffold, with iteration 1's commit ("EVAL-1 Page bounds for
1-based pages"); only a later plain `commit:` entry on this branch passes. A
fix left in the working tree, amended into iteration 1's commit, or committed
on a new branch fails here.
