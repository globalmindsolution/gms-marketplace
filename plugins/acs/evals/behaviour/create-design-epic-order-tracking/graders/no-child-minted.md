---
type: file_exists
path: '**/EVAL-2/**'
exists: false
---

The design never splits the epic into child partitions; minting children is
`/acs:create-ticket EVAL-1 --fan-out`'s job, after the design.
