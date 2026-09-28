---
type: llm
---

PASS if the final reply says both hooks were installed and reports that the
installed commit-msg hook accepted `EVAL-7: Add wishlist export` and
rejected `EVAL-7 Add wishlist export`, because the configured commit format
is `{ticket_id}: {summary}`.
FAIL if it reports the subject without the colon as accepted, says the hooks
enforce acs's default formats, claims it changed the settings or committed
anything, or asks the user a question.
