---
type: regex
target: files
pattern: '^schemas/|^docs/api/'
flags: m
match: not_contains
---

Documents only (ADR-0134). The repo keeps one JSON Schema per event, so
order.shipped will need one -- but /acs:create-impl-plan plans it from the
approved contract and /acs:code writes it. A schema written here is the
machine-readable contract this skill no longer produces.
