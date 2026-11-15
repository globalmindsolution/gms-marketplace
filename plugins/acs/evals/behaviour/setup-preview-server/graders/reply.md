---
type: llm
---

PASS if the final reply names the server it configured (`pnpm run dev`) and
its port (5173) and says it was written to .claude/launch.json.
FAIL if it claims a server or port the repo does not have, says nothing was
written, or asks the user a question.
