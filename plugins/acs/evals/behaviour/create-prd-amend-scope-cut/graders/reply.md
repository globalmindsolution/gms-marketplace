---
type: llm
---

PASS if the final reply reports an amend-mode run: order tracking moved to
Won't and Out of scope, everything else left unchanged, lists
docs/product/prd.md as an uncommitted local change for the user to review,
pointing at /acs:create-pr to commit it and open the PR, and points at
/acs:manage-roadmap to re-plan the roadmap that still schedules order tracking.
FAIL if it describes a rewritten or regenerated PRD, says it edited the
roadmap, says it committed,
pushed or opened a pull request, gives a PR number or URL, or asks the user a
question the request answered.
