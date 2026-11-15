---
type: llm
---

PASS if the final reply confirms that the default ticket prefix was kept and
that no CI checks were installed, without asking the user
to confirm either choice again.
FAIL if it asks the user a question the request already answered, says it
installed or enabled any CI check, or reports writing a custom ticket prefix.
FAIL if it asks the user for where acs should keep its state (a workspace path or folder): setup does not ask that.
