---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"type"\s*:\s*"epic"'
---

The allocate step mints a placeholder typed `task`; Step 3 rewrites the
ticket with the confirmed type. The request said epic in so many words, so a
ticket still typed task (or story) is the placeholder or a re-decided type.
