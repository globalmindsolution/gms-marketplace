---
type: regex
target: { source: file, path: docs/product/features/card-checkout/prd.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?implemented"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 1\n)'
---

Card checkout's one requirement is named by EVAL-1, merged on main, so its
delivery is `implemented` and the move is legal: the PRD reads `status:
implemented`, its version unchanged.
