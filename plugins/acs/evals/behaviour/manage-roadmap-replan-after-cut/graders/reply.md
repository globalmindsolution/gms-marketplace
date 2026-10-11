---
type: llm
---

PASS if the final reply reports a replan run: the Order tracking milestone and
its v2.6.0 row removed, Storefront and Checkout unchanged, the roadmap at
version 2 for the team to approve, docs/product/roadmap.md listed as an
uncommitted local change, pointing at /acs:create-pr to commit it.
FAIL if it says it changed the PRD, says it committed, pushed or opened a
pull request, gives a PR number or URL, or asks the user a question the
request answered.
