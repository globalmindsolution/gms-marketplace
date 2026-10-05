---
type: file_exists
path: .git/acs/state-machine/example-shop/runs/*/clarifications.json
---

With no ticket the clarification ledger is the run's own,
`runs/<run-id>/clarifications.json` (the run id is derived from the
invocation, so the glob does not name it). A run that never recorded the
relayed answers -- or wrote them somewhere else -- has none.
