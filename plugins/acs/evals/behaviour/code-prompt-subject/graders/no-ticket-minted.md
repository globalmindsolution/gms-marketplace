---
type: regex
target: files
pattern: 'example-shop/EVAL-\d+/ticket\.json'
match: not_contains
---

A prompt is a subject in its own right (§3.11): the run is keyed on the
prompt, and nothing mints a ticket for it. A run that detoured through
/acs:create-ticket, against the request, fails here.
