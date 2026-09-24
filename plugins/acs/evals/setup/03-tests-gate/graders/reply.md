---
type: llm
---

PASS if the final reply says the tests gate was installed, states the command
it will run, names the required status check `Tests & coverage`, and says the
workflow only blocks merges once branch protection requires it.
FAIL if it claims the tests passed in CI, or says the check already blocks
merges.
FAIL if it asks the user for a ticket prefix or for where acs should keep its state (a workspace path or folder): setup asks neither.
