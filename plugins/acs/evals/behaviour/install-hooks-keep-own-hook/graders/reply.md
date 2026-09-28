---
type: llm
---

PASS if the final reply says the commit-msg hook was installed, says the
pre-push hook was left untouched because a non-acs hook already exists (so
branch names are not checked locally until the user wires it in), and tells
the user to commit the newly created `.acs/ci/` files.
FAIL if it claims the pre-push hook was installed or updated, says it
committed anything, or asks the user a question.
