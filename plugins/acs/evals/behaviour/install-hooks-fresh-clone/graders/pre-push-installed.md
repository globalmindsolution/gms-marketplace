---
type: regex
target: { source: file, path: .git/hooks/pre-push }
pattern: 'check-conventions\.py[\s\S]*--mode pre-push'
---

And its pre-push hook checks the branch name and the pushed commit subjects:
with no existing hook to protect, both hooks are installed.
