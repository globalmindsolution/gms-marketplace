---
type: llm
---

PASS if the final reply says no hooks were installed because the
`ticket_prefix` in .acs/settings.json ("shop") is malformed -- it must be an
uppercase identifier such as `SHOP` -- and tells the user to fix it or
remove it to use the default, then re-run.
FAIL if it says hooks were installed, claims it changed the settings, or
asks the user a question.
