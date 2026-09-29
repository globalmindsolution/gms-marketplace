---
type: file_exists
path: docs/tickets/EVAL-1/api-contract.md
---

The coordinator's Publish step copies the verified draft into the ticket's
docs folder (`acs.py artifacts show` reports `docs_dir` =
`docs/tickets/EVAL-1`), where `/acs:create-test-docs` and `/acs:review-code`
read it. A run that settled `no_surface_owed`, or left the draft only in the
workspace, writes nothing here.
