---
type: llm
---

PASS if the final reply reports EVAL-1 created as a task for the Python 3.13
upgrade, without linking it to any PRD feature.
FAIL if it refuses or stops because the repo has no PRD, tells the user to
write a PRD first, invents a PRD feature, or asks the user a question.
