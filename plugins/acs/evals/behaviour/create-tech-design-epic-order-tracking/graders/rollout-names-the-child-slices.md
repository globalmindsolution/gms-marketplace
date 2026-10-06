---
type: regex
target: { source: file, path: docs/architecture/lld/order-tracking/EVAL-1/tech-design.md }
pattern: '^### Rollout & migration[ \t]*$(?:(?!^##?#? )[\s\S])*\b(?:child|children|slices?)\b'
flags: mi
---

For an epic the design is made at epic level and /acs:breakdown-ticket derives the
child breakdown from its `## Risks` › `### Rollout & migration` content
(its "Deriving the children"): the subsection names the child slices the prompt
asked for.
