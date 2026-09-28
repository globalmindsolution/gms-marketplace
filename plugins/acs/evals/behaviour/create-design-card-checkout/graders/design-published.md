---
type: file_exists
path: docs/tickets/EVAL-1/design.md
---

The coordinator's Publish step copies the reviewed draft into the ticket's
docs folder (`acs.py artifacts show` reports `docs_dir` =
`docs/tickets/EVAL-1`), which is what the `design_approved` predicate and
`/acs:code` look for. A draft left only in the workspace partition gates
nothing.
