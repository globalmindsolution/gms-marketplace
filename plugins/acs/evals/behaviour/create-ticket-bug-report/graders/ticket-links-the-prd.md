---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"features"\s*:\s*\[[^\]]*"customer-listing"'
---

The bug is filed against the PRD (ADR-0144): its `features` name the
customer-listing feature whose behaviour it reports. A requirement id is
optional for a bug, so only the feature is graded.
