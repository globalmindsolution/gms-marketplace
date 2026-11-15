---
type: llm
---

PASS if the final reply says card checkout's PRD was marked implemented and
order tracking's was not, because its requirement order-tracking/R1 is not
delivered yet (naming the open ticket EVAL-2 is welcome but not required:
the delivery reading lists requirements, not tickets), and points at
/acs:create-pr for the changed file.
FAIL if it claims order tracking was marked implemented, says it overrode the
delivery check, committed or pushed, or stops to ask the user a question
before finishing. Saying what the user could do next -- give a reason for an
override, or finish the tickets and re-run -- is not a question.
