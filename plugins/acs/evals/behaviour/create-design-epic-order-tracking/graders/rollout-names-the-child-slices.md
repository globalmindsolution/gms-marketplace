---
type: regex
target: { source: file, path: docs/architecture/lld/order-tracking/EVAL-1/design.md }
pattern: '^## Rollout/migration[ \t]*$(?:(?!^## )[\s\S])*\b(?:child|children|slices?)\b'
flags: mi
---

For an epic the design is made at epic level and the fan-out derives the
child breakdown from its Rollout/migration content (epic-fan-out.md step 4):
the section names the child slices the prompt asked for.
