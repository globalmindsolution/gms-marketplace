---
type: regex
target: { source: file, path: docs/architecture/lld/customer-listing/data/physical-schema.md }
pattern: '^status_by: "?acs"?\nstatus_at: "?\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ"?\nstatus_reason: "?[^\n]*the code matches'
flags: m
---

The move went through `acs.py design status --set implemented --by acs --reason
"<run-id>: the code matches"`, which records who, when and why (ADR-0130) --
never a hand edit of the front matter, which records none of them.
