---
type: file_exists
path: docs/tickets/EVAL-1/test-cases.md
---

The coordinator's Publish step copies the verified draft into the ticket's
docs folder (`acs.py artifacts show` reports `docs_dir` =
`docs/tickets/EVAL-1`), which is where `/acs:create-e2e-tests`'s gate and
`/acs:review-code` read it.
