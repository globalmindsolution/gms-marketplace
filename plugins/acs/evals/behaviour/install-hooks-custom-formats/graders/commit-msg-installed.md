---
type: regex
target: { source: file, path: .git/hooks/commit-msg }
pattern: 'check-conventions\.py[\s\S]*--mode commit-msg'
---

The hook delegates to the committed checker, which reads the committed
settings on every commit -- that is what makes the configured format, not a
format baked into the hook, the one enforced. A hand-written hook with its
own regex fails here, as does a clone with no hook at all.
