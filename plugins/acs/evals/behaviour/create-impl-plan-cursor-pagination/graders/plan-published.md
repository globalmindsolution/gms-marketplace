---
type: file_exists
path: docs/tickets/EVAL-1/plan.md
---

The coordinator's Publish step copies the verified draft to the ticket's docs
folder, which is where `/acs:code`'s gate looks for it (`acs.py artifacts
show` reports `docs_dir` = `docs/tickets/EVAL-1`). A plan left only in the
workspace draft, or written anywhere else, does not open the next gate.
