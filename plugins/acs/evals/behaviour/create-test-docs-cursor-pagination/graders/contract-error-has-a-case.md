---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/test-cases.md }
pattern: '\|[ \t]*TC-\d+[ \t]*\|[^\n]*invalid_cursor'
---

Every contract item needs at least one case "including its error and edge
shapes": the contract's `invalid_cursor` error must be the expectation of a
TC row, not just a mention in prose.
