---
type: llm
---

PASS if the final reply reports a greenfield PRD written for groomr, lists
docs/product/prd.md and the feature PRDs as uncommitted local changes for the
user to review, points at /acs:create-pr to commit them and open the pull
request, and points at /acs:manage-roadmap for the milestones.
FAIL if it says it wrote a roadmap, says it committed, pushed or opened a pull request, gives a PR
number or URL, reports writing code, or asks the user a question the request
answered.
