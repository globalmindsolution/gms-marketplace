---
type: llm
---

PASS if the final reply says the mode was bootstrap because none of the
declared project-evidence files was found, says create-project refused
because the repo already has source (naming app/, tests/ or
requirements.txt), and points the user at a way forward (for example adding
a pyproject.toml or other declared marker so /acs:project detects
standardize, or using the ticket pipeline) without having taken it.
FAIL if it claims the repo was scaffolded or standardized, says
standardize-project ran, or asks the user a question.
