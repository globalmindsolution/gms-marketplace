---
status: "implemented"
version: 1
tickets: []
feature: "acs"
---

# API — Delivery path

Where a change's delivery path is recorded, who reads it, and the ticket-time classification it replaced.

## Delivery path (ADR-0095)

**The path is recorded on the PLAN, not configured on the workflow.**
`ship.yaml` has no `delivery:` block: the path is a property of the work, and
the only reader who has seen the work when the judgement is made is
`/acs:create-impl-plan`. It writes the judgement into the plan's machine-
readable `## Contract` block:

```yaml
delivery_path: standard        # trivial | small | standard | complex
delivery_path_reason: "seven files across two modules, with a schema change"
```

`acs_lib/plan_contract.py` is the reader — `delivery_path(read(plan))` — and
`/acs:code`'s pre-hook is the one caller that acts on it, dispatching to the
matching leg. `run.json` records nothing about the path: it is derivable from
an artifact the run already has, and a second copy is a second thing to keep
true.

One judgement, made once from the plan. A resumed run re-reads the plan and
reaches the same answer, so a pipeline cannot end up half on one path and half
on another without the plan itself having changed — and an edited plan is an
unapproved plan, which the deep paths' approval brake already refuses.

**What this replaced.** MAR-56 put three optional fields on `ticket.json` —
`size` (`trivial|small|standard|large`), `stakes` (`low|normal|high`) and a
`lane` cache derived from them by `derive_lane` — mirrored onto
the run ledger and `tickets-index.json`. MAR-106 added an
`escalations` array on `code-state.json` run entries, a fixed 13-field event
appended by `record_escalation_event` at an iteration-start detection point,
so that a mid-run lane change was never silent. MAR-108 added
`confirm_deescalation`, the only writer able to lower those axes, unreachable
without an *answered* `clarify.py` reference.

All of it is retired. The axes were a guess made before anyone read the code;
the escalation ledger and the de-escalation writer existed only to make that
guess safe to revise mid-run. One judgement, made from the plan and recorded
once, needs none of them. A ticket from an older build that still carries
`size`, `stakes` or `lane` is read as if it did not.
