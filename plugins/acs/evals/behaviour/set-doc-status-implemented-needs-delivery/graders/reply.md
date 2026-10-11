---
type: llm
---

PASS if the final reply says card checkout's PRD was marked implemented and
order tracking's was not, because its requirement order-tracking/R1 is not
delivered yet (its ticket EVAL-2 is still open), and points at /acs:create-pr
for the changed file.
FAIL if it claims order tracking was marked implemented, says it overrode the
delivery check, committed or pushed, or asks the user a question.
