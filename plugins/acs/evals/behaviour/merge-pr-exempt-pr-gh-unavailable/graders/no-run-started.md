---
type: file_exists
path: .acs/state-machine/example-shop/runs/**
exists: false
---

The exempt mode "resolves no run and writes no partition, lock, pointer or
state" -- on success, and so certainly on a failure. A run directory means
the skill fell back to the ticket path (`acs step start --step merge-pr`
without `--pr`) or recorded a step for a PR that is nobody's ticket.
