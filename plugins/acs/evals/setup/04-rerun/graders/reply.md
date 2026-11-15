---
type: llm
---

PASS if the final reply recognises that acs was already set up here, shows or
summarises what is configured (the PAY ticket prefix and the ticket-link
check), and reports that nothing needed to change.
FAIL if it asks the user to choose a prefix or CI gates again, or reports
changing the prefix or installing a new gate.
FAIL if it asks the user for where acs should keep its state (a workspace path or folder): setup does not ask that.
