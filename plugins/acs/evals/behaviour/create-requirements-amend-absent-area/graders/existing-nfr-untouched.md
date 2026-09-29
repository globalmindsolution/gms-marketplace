---
type: regex
target: { source: file, path: docs/requirements/non-functional/performance.md }
pattern: '^# Performance\n\n- API p95 latency MUST stay under 300 ms \{#p95\}\n(?![\s\S])'
---

The existing non-functional file is byte-identical too: the amendment is a
functional area, and the new orders listing adds no NFR item.
