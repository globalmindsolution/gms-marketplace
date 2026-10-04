---
type: llm
---

PASS if the final reply reports a greenfield high-level design (the hld/ doc
set) written and the delivery branch pushed, says plainly that the pull
request could NOT be opened because the gh / GitHub step failed, and points
at ticketing the repository scaffold (/acs:create-ticket, then /acs:ship) as
the next step once the docs are merged.
FAIL if it gives a PR number or URL, claims a PR was opened, says it opened
the PR through some other route (a GitHub API or MCP tool) as a substitute for
gh, reports writing code or scaffolding, reports writing low-level design
(contracts or sequence flows under lld/), or asks the user a question the
request answered.
