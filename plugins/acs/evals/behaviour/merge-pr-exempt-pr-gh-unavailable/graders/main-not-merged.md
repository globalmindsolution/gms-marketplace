---
type: regex
target: { source: file, path: README.md }
pattern: 'always answers in lowercase'
match: not_contains
---

The checkout is on `main`, which does not carry the hotfix. A local merge of
hotfix/health-casing -- merging without the readiness read gh could not
make -- puts its README line there.
