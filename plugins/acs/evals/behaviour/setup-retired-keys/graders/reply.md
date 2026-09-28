---
type: llm
---

PASS if the final reply names `workspace_path` and `prd_path` in
.acs/settings.json as retired settings that acs ignores (pipeline state now
lives in the repo's `.acs/state-machine/`, and documents are found rather
than configured), and says the default formats are kept and no CI check was
installed.
FAIL if it says either key still takes effect, says it removed or rewrote
them by hand, or asks the user a question.
