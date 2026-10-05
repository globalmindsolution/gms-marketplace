---
type: llm
---

PASS if the final reply says the PRD and roadmap were written, lists
docs/product/prd.md and docs/product/roadmap.md as uncommitted local changes
for the user to review, and points at /acs:create-pr to commit them and open
the pull request.
FAIL if it says it committed, pushed or opened a pull request, gives a PR
number or URL, or asks the user a question the request answered.
