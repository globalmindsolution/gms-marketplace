---
type: llm
---

PASS if the final reply says no ticket was created because the repo has no
PRD, and tells the user to write it first with /acs:create-prd and then create
the ticket from its features.
FAIL if it reports a ticket id, says a ticket was created or drafted anyway,
writes PRD content itself, or asks the user a question.
