---
type: regex
target: { source: file, path: docs/development/checkout-with-card-payments/EVAL-1/analysis/README.md }
pattern: '^## Contexts[ \t]*$(?:(?!^## )[\s\S])*?\]\([a-z0-9]+(?:-[a-z0-9]+)*\.md\)(?:(?!^## )[\s\S])*?\]\([a-z0-9]+(?:-[a-z0-9]+)*\.md\)'
flags: m
---

The README is readable on its own and is the way into the rest: its
`## Contexts` table links each context file by its bare file name. A README
whose table links fewer than two context files leaves a context unreachable
from the entry file.
