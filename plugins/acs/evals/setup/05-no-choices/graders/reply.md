---
type: llm
---

PASS if the final reply asks the user to choose whether to keep or change the
branch/commit/PR formats and which CI checks (if any) to install. The choices
may be a list or prose, and it may first report what it found in the repo.
FAIL if it applied a configuration or installed a CI check without the user
choosing.
FAIL if it asks the user for a ticket prefix or for where acs should keep its state (a workspace path or folder): setup asks neither.
