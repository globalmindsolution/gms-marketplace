---
type: regex
target: last_message
pattern: '/acs:update\W+failed'
flags: i
---

Step 2: with both the `gh` release list and the raw-file fallback failing,
the outcome is `failed`, stated in the completion block's header
(`## /acs:update · failed`). A run that reports `completed` claimed a version
comparison it could not make.
