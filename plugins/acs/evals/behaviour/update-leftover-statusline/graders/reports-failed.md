---
type: regex
target: last_message
pattern: '/acs:update\W+failed'
flags: i
---

Offline, both release lookups fail and Step 2 stops the run `failed` (the
completion block's header). A `completed` run claimed a version comparison it
could not make.
