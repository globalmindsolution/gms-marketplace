---
type: regex
target: { source: file, path: docs/architecture/lld/order-tracking/EVAL-1/api-contract.md }
pattern: '^## Contract files[ \t]*$(?:(?!^## )[\s\S])*schemas/events/'
flags: m
---

`## Contract files` names the machine-readable file(s) this run touched, not
"no machine-readable contracts".
