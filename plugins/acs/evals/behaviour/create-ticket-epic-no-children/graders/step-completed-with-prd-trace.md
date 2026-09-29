---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-ticket/state.json }
pattern: '"feature"\s*:\s*"[^"]*(?:F3|[Oo]rder [Tt]racking)[\s\S]*"status"\s*:\s*"completed"'
---

The mandatory Finish ran: result.json's `states.prd_trace.feature` names the
PRD feature the epic traces to (F3, Order tracking), and
`post-create-ticket.py` accepted it and recorded the invocation `completed`.
