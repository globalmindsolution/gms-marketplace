---
type: regex
target: { source: file, path: docs/architecture/lld/orders/data/physical-schema.md }
pattern: '\b(?:CREATE|ALTER|DROP)\s+(?:TABLE|INDEX)\b'
match: not_contains
---

The Migration outline is ordered prose -- what is created, in what order, how
it rolls back -- never migration code. A DDL statement in the document is the
migration written early under another name. (A regex on a missing file
fails, so this also fails a run that never wrote the schema.)
