---
status: "implemented"
version: 1
tickets: []
feature: "acs"
---

# API — Coordinator ↔ subagent messages

The JSON messages a step's coordinator and its subagents exchange, and the schemas that validate them.

## Coordinator ↔ subagent (JSON, `plugins/acs/schemas/`)

| Message | Direction | Key content |
|---------|-----------|-------------|
| the task document | coordinator → subagent | skill, step, run id, iteration; objective, input file refs, constraints, context (clarifications, prior findings) |
| the result document | subagent → coordinator (final message, nothing after) | status, output file refs (incl. the iteration artifact), findings, errors, questions |
| the handoff | step coordinator → /ship | ≤ ~1 KB summary, artifact refs, next step, questions on `needs_input` |

**Messages are JSON, validated in the hook.** The XSD layer —
`acs-messages.xsd` and the `validate_xml.py` that enforced it — is removed in
v0.5.0: a second schema language bought nothing the first one did not already
carry, and the in-process XML validator existed only to avoid a subprocess per
message. The contract's declarations are now the fourteen JSON Schemas under
`plugins/acs/schemas/`, `result.schema.json` among them, and `acs.py result
validate` checks a step's result document before its post-hook consumes it.
Constraint names stay typed — a misspelled delegation key fails at the
coordinator rather than arriving at the subagent as an absent value.

**No usage in the message contract.** The self-estimated `<metrics>`
element is gone from the result document's shape — `result.schema.json` does
not declare it, so a stray `<metrics>` element is rejected as an undeclared
property. The flat `tokens`, `role_usage`, `model_usage`, `cost_usd`,
`cost_basis` and `api_duration_ms` keys are legacy: accepted so an older
coordinator's result still validates, and ignored. Nothing measures usage in
their place either — acs records no token count, no dollar figure and no
`run.json` `totals`
([ADR 0104](../../../adr/0104-no-usage-dashboards-no-usage-recording.md)).
