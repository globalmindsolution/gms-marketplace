---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"path"\s*:\s*"docs/product/features/health-check/analysis/README\.md"'
---

The references are found from the ticket's FEATURE, never searched for: the
request traces to the PRD's Health check feature, so the ticket carries
`features: ["health-check"]` and the layout lookup lists that feature's living
analysis. A ticket saved without its feature only gets the PRD fallback.
