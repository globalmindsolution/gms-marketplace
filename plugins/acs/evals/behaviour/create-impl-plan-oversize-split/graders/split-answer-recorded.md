---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/clarifications.json }
pattern: '"skill"\s*:\s*"create-impl-plan"[^{}]*"answer"\s*:\s*"[^"]*[Ss]plit'
---

Split-answer termination (ADR 0069): the user's answer to the oversize
question is recorded with `clarify.py add` like any other answer, BEFORE the
run acts on it.
