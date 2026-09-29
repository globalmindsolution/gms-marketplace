---
type: regex
target: { source: file, path: docs/operations/observability.md }
pattern: '^(?=[\s\S]*^#{1,3}\s+SLO/SLA notes)(?=[\s\S]*99\.9\s?%)(?=[\s\S]*300\s?ms)'
flags: m
---

Grounded in the PRD's non-functional requirements (the slice
`DOC_SETS["operations"]` reads): the SLO section states the 99.9%
availability and the 300 ms p95 targets. The untailored template carries
neither.
