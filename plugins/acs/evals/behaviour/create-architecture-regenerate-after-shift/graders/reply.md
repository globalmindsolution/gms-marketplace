---
type: llm
---

PASS if the final reply reports a re-run that regenerated the existing
high-level design in place -- the export-worker and Redis removed from the
HLD views, the orders API added -- lists the changed files as uncommitted
local changes, and points at /acs:create-pr to commit them and open the pull
request.
FAIL if it describes writing a new doc set elsewhere, keeps the removed
worker or Redis in the HLD, reports editing, adding or deleting low-level
design under lld/ (a contract or a flow file), says it committed, pushed or
opened a pull request, gives a PR number or URL, or asks the user a question
the request answered.
