---
type: file_exists
path: docs/tickets/EVAL-1/analysis.md
---

The coordinator's Publish step copies the verified draft to the ticket's docs
folder (`acs.py artifacts show` reports `docs_dir` = `docs/tickets/EVAL-1`,
because the run directory is a checkout). A draft left only in the workspace
partition, or an analysis written anywhere else, is not what the next gates
(`/acs:create-api-contract`, `/acs:create-impl-plan`) look for.
