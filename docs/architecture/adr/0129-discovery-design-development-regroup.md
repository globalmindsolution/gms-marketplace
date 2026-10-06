# 0129 — Discovery is the PRD and the feature analysis; tickets are a Utility

**Status**: Accepted — amended by [0130](0130-prd-versions-and-set-doc-status.md) (Utility gains `/acs:set-doc-status`) and [0131](0131-ticket-handoff-between-members.md) (Utility's `/acs:handoff` is a team handoff, member to member) and [0134](0134-api-contract-is-a-design-document.md) (`/acs:create-api-contract` no longer runs as a `ship.yaml` step) and by [0138](0138-breakdown-ticket-and-typed-ticket-authors.md) (Utility gains `/acs:breakdown-ticket`) · **Date**: 2026-10-04

**Amends**: [0118](0118-discovery-design-development-phases.md) (which skills each
phase groups: `/acs:analyze-requirements` joins Discovery, `/acs:create-ticket` —
and `breakdown-ticket` when it ships — moves to Utility).

## Context

ADR-0118 grouped the skills as Discovery (`create-prd`, `create-ticket`,
`breakdown-ticket`), Design (the solution-architecture skills) and Development
(what `/acs:ship` drives, plus `merge-pr`). Its premise was that the work after
the PRD starts by cutting tickets.

ADR-0128 removed that premise. A ticket is now one container of requirements
among three, no skill requires one, and `/acs:analyze-requirements` analyses a
PRD feature, a prompt or an attached specification with no ticket at all, writing
the feature's living analysis beside the PRD. Tickets are cut at more than one
point — after the PRD and a feature's analysis (for design work or for
implementation), and again after a design (for implementation) — so they are not
a phase of their own. The plugin README meanwhile still grouped the skills as
Design, Build, Test and Ship, which matched neither ADR.

## Decision

The skills group into five reader's-aid groups; the code still knows skills, not
phases, and `workflows/ship.yaml` alone states the order steps run in.

| Group | Skills | What it settles |
|---|---|---|
| **Discovery** | `create-prd`, `analyze-requirements` | what to build: the PRD, and a feature's analysis (ticketless, `<prd_dir>/features/<feature>/analysis.md`) |
| **Design** | `create-architecture`, `create-api-contract`, `create-data-design`, `create-flows`, `create-design` | how to build it: the HLD, the living LLD, and the per-change design records |
| **Development** | `/acs:ship` and its steps — `analyze-requirements` on a ticket or a prompt first, `create-impl-plan`, `create-test-docs`, `code` (and its four legs), `review-code`, `docs-sync`, `create-e2e-tests`, `run-e2e-tests`, `create-pr` — plus `merge-pr` | building, reviewing and landing one change |
| **Audit** | `audit-design`, `audit-security` | unchanged (ADR-0123) |
| **Utility** | `setup`, `update`, `release`, `handoff`, `create-ticket` (and `breakdown-ticket` when it ships) | configuring the plugin, cutting releases, handing a session off, and making tickets |

`/acs:analyze-requirements` is listed once, under Discovery, and is also
Development's first step; `/acs:create-api-contract` is listed under Design and
still runs as a `ship.yaml` step until it moves out of the list (ADR-0118 §4).

## Consequences

- The plugin README's skill tables, `docs/requirements/functional/skills.md`'s
  groups and the PRD use these five groups. No skill, gate, hook or workflow step
  changes; this decision is documentation.
- A ticket is made when the work needs one — to track it, to sync it to a
  tracker, or to fan an epic out — not as the entry to a phase.
- The skill and agent counts are unchanged.
