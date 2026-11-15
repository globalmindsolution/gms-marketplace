---
type: regex
target: { source: file, path: docs/architecture/lld/customer-listing/api/customers.md }
pattern: '^-{3}\nstatus: "?approved"?\nversion: 1\n'
---

An approved document is never silently rewritten: with the question
unanswered it stays exactly as the team approved it -- not bumped back to
`proposed` (answer (a) was never given) and not flipped to `implemented` (the
code does not match it).
