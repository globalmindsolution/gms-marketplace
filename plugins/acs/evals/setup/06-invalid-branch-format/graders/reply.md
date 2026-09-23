---
type: llm
---

PASS if the final reply explains that the branch name format must include the
ticket id because acs finds the current ticket from the branch name, and
either keeps the default format or offers one that contains `{ticket_id}`.
FAIL if it reports saving `{type}/{slug}`, or reports setup as completed with
a branch format the user did not choose.
FAIL if it asks the user for a ticket prefix or for where acs should keep its state (a workspace path or folder): setup asks neither.
