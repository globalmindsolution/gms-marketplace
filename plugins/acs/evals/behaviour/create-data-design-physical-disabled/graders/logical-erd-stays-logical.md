---
type: regex
target: { source: file, path: docs/architecture/lld/orders/data/logical-erd.md }
pattern: '^## (?:Tables|Indexes and constraints|Migration outline)[ \t]*$|\bCREATE\s+(?:TABLE|INDEX)\b'
flags: m
match: not_contains
---

The logical ERD is database-agnostic: it has no Tables, Indexes and
constraints or Migration outline section, and no DDL. A run that folded the
disabled physical schema into it wrote the disabled type anyway, under the
enabled one's name. (Prose that mentions the key strategy is not caught.)
