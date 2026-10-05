---
type: regex
target: { source: file, path: docs/architecture/lld/checkout-with-card-payments/EVAL-1/design.md }
pattern: '^## Architecture[ \t]*$(?:(?!^## )[\s\S])*^```mermaid[ \t]*$(?:(?!^## )[\s\S])*^### Architecture conformance'
flags: m
---

Under Architecture: a Mermaid diagram for the new checkout flow (the ticket
adds a runtime flow through the payments gateway), then the `### Architecture
conformance` call -- "Conforms to ..." or the list of doc-set changes
`/acs:code` must apply.
