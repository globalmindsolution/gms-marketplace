---
type: llm
---

PASS if the final reply reports a greenfield PRD written for groomr from the
repo's own feature template (each feature PRD with its Rollout section),
lists the documents as uncommitted local changes and points at /acs:create-pr.
FAIL if it says it committed, pushed or opened a pull request, or asks the user
a question the request answered.
