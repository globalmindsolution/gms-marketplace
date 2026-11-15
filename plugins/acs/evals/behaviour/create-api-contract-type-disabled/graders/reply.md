---
type: llm
---

PASS if the final reply says /acs:create-api-contract wrote nothing for EVAL-1
because the api-contract LLD type is not enabled in design.lld_types, and
that the step was recorded completed (type_disabled).
FAIL if it reports writing or revising an interface document, a run record, a
machine-readable contract or code, or asks the user a question.
