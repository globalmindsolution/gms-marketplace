---
type: regex
target: last_message
pattern: '/acs:create-ticket EVAL-1'
---

For an epic the next step is the fan-out -- `/acs:create-ticket EVAL-1`
(--fan-out) -- then `/acs:code` on each child. Pointing an epic at
`/acs:code EVAL-1` is the story path.
