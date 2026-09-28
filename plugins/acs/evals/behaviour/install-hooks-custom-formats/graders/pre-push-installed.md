---
type: regex
target: { source: file, path: .git/hooks/pre-push }
pattern: 'check-conventions\.py[\s\S]*--mode pre-push'
---

The pre-push hook enforces the configured `{ticket_id}/{slug}` branch name
the same way.
