---
type: regex
target: last_message
pattern: '(nothing (to|was) (hand|send|sen)|no (current )?run|no ticket)[\s\S]*/acs:handoff [<A-Z]|/acs:handoff [<A-Z][\s\S]*(nothing (to|was) (hand|send|sen)|no (current )?run|no ticket)'
flags: i
---

The reply says there is nothing to hand off from this checkout and how to send
one: `/acs:handoff <ticket-id>` (or a real id).
