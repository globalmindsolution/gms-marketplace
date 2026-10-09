---
type: file_exists
path: '**/ticket.json'
exists: false
---

No ticket was minted: the pre-gate refuses `acs step start --allocate` before
an id is spent, and nothing writes a ticket.json around the refusal.
