---
type: regex
target: files
pattern: '^docs/architecture/lld/'
flags: m
match: not_contains
---

The skill writes the high-level design only: contracts, schemas and sequence
flows are the low-level design the Design skills write per ticket under
`lld/<feature>/` (ADR-0118). A run that creates any file under `lld/` wrote
someone else's documents.
