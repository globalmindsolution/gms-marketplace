---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/analysis/README.md }
pattern: '^## Contexts[ \t]*$(?:(?!^## )[\s\S])*\]\(customer-listing\.md\)'
flags: m
---

The README is readable on its own, and its `## Contexts` table is how a
reader finds the rest: each context file linked by its bare file name. A
README whose table does not link `customer-listing.md` leaves the impact map
unreachable from the entry file.
