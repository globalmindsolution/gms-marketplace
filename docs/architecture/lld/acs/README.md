# LLD — acs

The low-level design of the PRD feature
[acs (Autonomous Coding Skills)](../../../product/prd.md#feature-acs-autonomous-coding-skills).
The binding shapes live in machine-validated files — the JSON Schemas under
`plugins/acs/schemas/` — and the canonical detail is
`plugins/acs/docs/INTERNALS.md`; these documents are the index to them.

## api — interface contracts

| Document | Interface |
|----------|-----------|
| [coordinator-subagent.md](api/coordinator-subagent.md) | the JSON task, result and handoff documents between a coordinator and its subagents |
| [cli.md](api/cli.md) | the deterministic layer's CLI, its exit codes, and the Claude Code hook events |
| [delivery-path.md](api/delivery-path.md) | the delivery path recorded on the plan (ADR-0095) |
| [guard-audit.md](api/guard-audit.md) | the file-map guard's denial audit trail |
| [state-files.md](api/state-files.md) | the `states` keys one step hands the next step's gate |
| [settings.md](api/settings.md) | the consumer repo's settings, and the conformance chain |

## flows — sequence and state diagrams

| Document | Flow |
|----------|------|
| [hook-gated-skill-run.md](flows/hook-gated-skill-run.md) | every hooked skill run, gated by its pre- and post-hook |
| [ship-pipeline.md](flows/ship-pipeline.md) | `/acs:ship` driving the declared pipeline |
| [state-ticket.md](flows/state-ticket.md) | the ticket's status lifecycle |
| [ticket-lifecycle.md](flows/ticket-lifecycle.md) | `/acs:merge-pr` merging a ticket and archiving its partition |
| [ticket-id-reconciliation.md](flows/ticket-id-reconciliation.md) | the first ticket-id allocation's reconciliation gate |
| [state-root-resolution.md](flows/state-root-resolution.md) | how a gated run resolves its workspace root |
| [setup-state-root-setup.md](flows/setup-state-root-setup.md) | `/acs:setup` setting up the workspace root |
| [file-map-guard-deny.md](flows/file-map-guard-deny.md) | the file-map guard's deny path |
| [github-call-failure-policy.md](flows/github-call-failure-policy.md) | how a failed `gh` call is classified |
| [tests-coverage-gate.md](flows/tests-coverage-gate.md) | this repo's `Tests & coverage` required check |
| [enforce-e2e-merge-gate.md](flows/enforce-e2e-merge-gate.md) | a red e2e suite as a merge brake |
| [release-cut.md](flows/release-cut.md) | `/acs:release` cutting a version |

A document's `.evidence.md` sidecar beside it holds its code-evidence citations.

## Change records

| Folder | Record |
|--------|--------|
| [MAR-4/](MAR-4/runtime-coupling-inventory.md) | the runtime-coupling seam inventory of the rejected multi-runtime epic |
