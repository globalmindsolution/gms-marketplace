---
type: llm
---

PASS if the final reply reports the wishlist analysis (version 2) and the two
wishlist LLD documents (version 1) moved from proposed to approved, lists
those files as uncommitted local changes, and points at /acs:create-pr to
commit them and open the PR.
FAIL if it says the checkout documents, the PRD or the HLD changed, reports a
version bump, says it committed, pushed or opened a pull request, or asks the
user a question the request answered.
