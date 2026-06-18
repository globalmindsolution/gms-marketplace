# Documentation

Product documentation for the **GMS Marketplace**, organized as the doc sets
the acs workflow maintains across the **software development lifecycle**. Each set is normative
for one concern and answers one question — none replaces another. Together they
cover define → specify → design → decide → **verify → release & operate**.

| Lifecycle phase | Set | Question it answers |
|-----------------|-----|---------------------|
| Define | [product/](product/) | WHY & WHAT, prioritized — vision, goals, features, product NFRs |
| Specify | [requirements/](requirements/) | the detailed, testable behavior (every MUST/SHOULD/MAY) |
| Design | [architecture/](architecture/) | HOW the system is structured — HLD (C4, data model, deployment, tech stack) + LLD (flows, contracts) |
| Decide | [adr/](adr/) | WHY each structural choice was made |
| **Verify** | [quality/](quality/) | HOW correctness is assured — test strategy, coverage policy, the release gate |
| **Release & operate** | [operations/](operations/) | HOW it ships and runs — release process, runbooks, observability, incident response |

Conformance flows top to bottom: **PRD → architecture → design → specs → code →
verify → release**, each level checked against the one above it. On conflict, the
PRD wins on intent and prioritization, the requirements set wins on behavior, the
relevant ADR records how the choice was settled, and a release ships only after
the [quality](quality/) gate passes.

## Cross-cutting & contributor docs

These sit outside the lifecycle sets (root files follow GitHub's conventions so
they're auto-discovered):

| Concern | Where |
|---------|-------|
| Security policy | [`SECURITY.md`](../SECURITY.md) (root) |
| How to contribute / develop the plugin | [`CONTRIBUTING.md`](../CONTRIBUTING.md) (root) + [`plugins/acs/docs/`](../plugins/acs/docs/) (INTERNALS, AUTHORING) |
| Install / usage / troubleshooting | [`plugins/acs/README.md`](../plugins/acs/README.md) |

> This repo dogfoods the marketplace on itself: the **acs** plugin is used as
> the agentic workflow tool for all active development work here, so these docs
> are also acs's own product docs — the same sets acs maintains for any
> consumer repo.
