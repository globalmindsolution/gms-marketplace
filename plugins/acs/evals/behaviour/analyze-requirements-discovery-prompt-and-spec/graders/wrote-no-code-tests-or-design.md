---
type: regex
target: files
pattern: '^(?:src|tests|docs/architecture)/'
flags: m
match: not_contains
---

Discovery analyzes; it never implements, and it never designs -- a design
is /acs:create-tech-design's, run when the user asks for one (ADR-0139).
