---
type: llm
---

PASS if the reply says the document templates were copied into .acs/templates/
for the team to edit (and commit), and that no CI was installed.
FAIL if it says CI was installed, asks the user a question the request
answered, or claims it committed.
