---
type: llm
---

PASS if the final reply says no ticket was created for the wishlist because
the repo has no PRD to make it from, and tells the user to write the PRD first
with /acs:create-prd and then create the ticket from its features.
FAIL if it reports a ticket created or drafted anyway (as a story or relabelled
as a task), writes PRD content itself, or asks the user a question.
