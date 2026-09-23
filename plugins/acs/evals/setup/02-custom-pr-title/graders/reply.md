---
type: llm
---

PASS if the final reply names the required status check `Branch / PR / commit
conventions`, says the workflow only blocks merges once branch protection
requires that check, and either gives the command for a repo admin to run or
says an admin must add it.
FAIL if it claims branch protection was changed or enabled, or says the check
already blocks merges.
FAIL if it asks the user for a ticket prefix or for where acs should keep its state (a workspace path or folder): setup asks neither.
