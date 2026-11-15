---
type: regex
target: { source: file, path: docs/architecture/lld/checkout-with-card-payments/EVAL-1/tech-design.md }
pattern: '^-{3}\nstatus: "?proposed"?\nversion: 1\ntickets:[^\n]*\n(?:  - [^\n]*\n)*feature: "?checkout-with-card-payments"?\n'
---

The published hand-off opens with its ADR-0122 version front matter, written by
`acs.py design init` and copied with the reviewed bytes: `proposed` at
version 1, naming the ticket and the feature — the record the team moves to
`approved` with `/acs:set-doc-status`. A hand-written or missing block, or a
design published already `approved`, fails.
