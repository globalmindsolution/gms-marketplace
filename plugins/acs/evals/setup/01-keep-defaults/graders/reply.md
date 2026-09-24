---
type: llm
---

PASS if the final reply confirms that the default branch, commit and PR title
formats were kept and that no CI checks were installed, without asking the user
to confirm either choice again.
FAIL if it asks the user a question the request already answered, says it
installed or enabled any CI check, or reports writing custom formats.
FAIL if it asks the user for a ticket prefix or for where acs should keep its state (a workspace path or folder): setup asks neither.
