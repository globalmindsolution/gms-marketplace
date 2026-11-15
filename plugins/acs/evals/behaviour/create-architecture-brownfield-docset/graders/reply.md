---
type: llm
---

PASS if the final reply says the high-level design (the hld/ doc set) was
written, lists the files as uncommitted local changes for the user to review,
and points at /acs:create-pr to commit them and open the pull request.
FAIL if it says it committed, pushed or opened a pull request, gives a PR
number or URL, reports writing low-level design (contracts or sequence flows
under lld/), or asks the user a question the request answered.
