---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/clarifications.json }
pattern: '"question"\s*:\s*"[^"]*(?:needs?|requires?|warrant)[^"]*\bdesign\b'
flags: i
match: not_contains
---

Whether a design is needed is never a question the analysis takes to the
user (ADR-0139): the user runs /acs:create-tech-design when they want one.
The ledger holds the relayed answers, and nothing asking for a design call.
