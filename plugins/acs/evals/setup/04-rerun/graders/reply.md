---
type: llm
---

PASS if the final reply recognises that acs was already set up here, shows or
summarises what is configured (the custom PR title format and the convention
check), and reports that nothing needed to change.
FAIL if it asks the user to choose formats or CI gates again, or reports
changing a format or installing a new gate.
FAIL if it asks the user for a ticket prefix or for where acs should keep its state (a workspace path or folder): setup asks neither.
