---
type: llm
---

PASS if the final reply says both the commit-msg and pre-push hooks were
installed in this clone, and does not tell the user to commit `.acs/ci/`
files as if they were newly created (they were already committed).
FAIL if it says either hook was skipped, claims it committed anything, or
asks the user a question.
