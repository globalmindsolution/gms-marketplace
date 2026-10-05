---
type: llm
---

PASS if the final reply reports a greenfield high-level design (the hld/ doc
set) written and left as uncommitted local changes, points at /acs:create-pr
to commit them and open the pull request, and points at ticketing the
repository scaffold (/acs:create-ticket, then /acs:ship) as the next step.
FAIL if it says it committed, pushed or opened a pull request, gives a PR
number or URL, reports writing code or scaffolding, reports writing low-level
design (contracts or sequence flows under lld/), or asks the user a question
the request answered.
