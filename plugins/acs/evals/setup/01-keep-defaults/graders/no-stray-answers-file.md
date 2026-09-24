---
type: regex
target: files
pattern: '(^|/)answers[^/]*\.json$'
flags: m
match: not_contains
---

Setup's answers go to the wizard on stdin. A file left in the repo is an
untracked artefact the user has to notice and delete.
