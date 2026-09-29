---
type: llm
---

PASS if the final reply names the required status check `E2E suite`, says
the workflow only blocks a merge once branch protection requires that check,
and gives the command for an admin to run or says an admin must add it.
FAIL if it claims branch protection was changed, says the gate already blocks
merges, or asks the user a question.
