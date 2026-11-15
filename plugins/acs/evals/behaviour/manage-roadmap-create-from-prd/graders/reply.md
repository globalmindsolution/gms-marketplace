---
type: llm
---

PASS if the final reply reports a create-mode run, lists the three milestones
with their versions and `planned` status, names docs/product/roadmap.md as an
uncommitted local change for the user to review, and points at /acs:create-pr
to commit it and open the pull request.
FAIL if it says it committed, pushed or opened a pull request, gives a PR
number or URL, says it changed the PRD, or asks the user a question the
request answered.
