# 0135 — `/acs:create-design` becomes `/acs:create-tech-design`: a versioned hand-off document for team review, approved with `/acs:set-doc-status`

**Status**: Accepted — amended by [0139](0139-tickets-carry-no-design-flag.md) (the `needs_design` brake is gone; `design_requirement` becomes `design_source`) · **Date**: 2026-10-05

**Amends**: [0118](0118-discovery-design-development-phases.md) (the Design
phase's per-change skill is renamed `/acs:create-tech-design`, and its document
`tech-design.md`) and [0130](0130-prd-versions-and-set-doc-status.md) (§4:
`acs.py design list` now lists a run's `tech-design.md` from the per-run
Design folders it used to skip, so `/acs:set-doc-status` can approve it).

## Context

`/acs:create-design` predates the low-level design. When it was written, its
`design.md` was the only design document a change had: context, options, a
decision, then an "architecture" section that held the components, interfaces,
data model and Mermaid sequence diagrams of the change. Since then the Design
phase has filled in around it. `/acs:create-architecture` keeps the HLD views
(ADR-0121). `/acs:create-api-contract`, `/acs:create-data-design` and
`/acs:create-flows` keep a feature's living `lld/<feature>/{api,data,flows,components}/`
documents, versioned and checked for gaps (ADR-0122, ADR-0126, ADR-0134). So
`design.md`'s architecture section restated, unversioned, what those documents
already held at a version, and nothing checked that the two agreed.

Its name also stopped saying what it is. "Design" is the name of the phase, of
the five skills in it and of the HLD/LLD set. The document this skill writes is
the one a team reads before it lets implementation start: the decision and the
options weighed, the design views the change touches, the risks and the open
questions, in one place. That is a technical design hand-off, and a reader
looking for it should not have to know that "design.md" means that one and not
the `lld/` folder beside it.

And its approval was not the team's. The design reviewer's pass published the
document; nobody recorded that the team had read and accepted it. ADR-0130 gave
every versioned document an approver record and a skill to move its status, but
`design.md` carried no version block, and `acs.py design list` skipped the
per-run folder it lives in, so `/acs:set-doc-status` could not see it.

## Decision

1. **Rename, no alias.** The skill is `/acs:create-tech-design`. Its agents are
   `create-tech-design-designer` (role `designer`) and
   `create-tech-design-reviewer` (role `reviewer`, formerly `design-reviewer`).
   Its hooks are `pre-create-tech-design.py` and `post-create-tech-design.py`,
   and its gate is `gate_create_tech_design` in `gates.SUBJECT_GATES` — the same
   brake as before: `needs_design` from the refined requirements or the ticket,
   epics allowed. `/acs:create-design` no longer exists; no skill answers to the
   old name. `design_requirement` keeps its name. The Design phase lists
   `create-architecture`, `create-api-contract`, `create-data-design`,
   `create-flows`, `create-tech-design`, in that order.
2. **The document is `tech-design.md`**, still one per change, in the run's
   Design folder `<architecture_dir>/lld/<feature>/<id>/` (ADR-0128) or kept
   local by the share-or-keep-local choice (ADR-0132). Its draft is
   `steps/create-tech-design/tech-design.md`. The run artifact keeps the key
   `design` (`acs.py artifacts show design`), with `tech-design` accepted as an
   alias.
3. **It is a hand-off for team review**, in six sections, in order:
   `## Decision & options` (context, the options considered, the decision and
   its rationale); `## HLD views affected` (excerpts of the `hld/` views the
   change touches, each linked at its version); `## LLD` with `### API`,
   `### Data`, `### Flows` and `### Components` (snapshots of the feature's
   living `lld/<feature>/` documents, each linked at its version, or "none yet"
   with the skill that would write it); `## NFRs`; `## Risks` (rollout and
   migration included); `## Open questions`. An epic fills every section; a
   story or task fills those it needs and marks the rest "n/a" with the reason.
   The snapshots point at the living documents rather than redesign them:
   `/acs:create-tech-design` still writes no `lld/<feature>/` document of its own.
4. **The reviewer checks across documents.** Beside its existing dimensions the
   reviewer judges cross-category consistency — every operation a flow names is
   in the api document, every entity it names is in the data document — and
   snapshot freshness: each linked version is the document's current version.
5. **It is versioned and approved like the other Design documents.**
   `tech-design.md` opens with ADR-0122's front matter (`status: proposed`,
   `version`, `tickets`, `feature`), written only through `acs.py design init`
   for a new file and `design bump` for a revised one. `acs.py design list`
   lists it in its feature's Design group — from a per-run folder
   `lld/<feature>/<id>/` it takes `tech-design.md` only, labelled with the
   run's key — so the team approves it with `/acs:set-doc-status approved
   <feature>`. The skill's report ends there: approve the hand-off, then
   `/acs:create-impl-plan`. `/acs:create-impl-plan` reads `tech-design.md` and
   states its status in its report; a document that is not approved is a
   warning, not a block.
6. **Old documents and old runs are still read.** Every reader resolves
   `tech-design.md` first and falls back to `design.md`, and to the step folder
   `steps/create-design/`, when the new name is absent: a design published before
   this change, or a run started under the old skill, is read where it is. Nothing
   writes `design.md` any more; a re-design of a change that has one writes
   `tech-design.md` beside it.
7. **Settings follow the rename.** `models.create-design` becomes
   `models.create-tech-design` with the agent keys `designer` and `reviewer`.
   `migrate_settings` renames an existing `models.create-design` block, and its
   `design-reviewer` key inside it, on load, so a repo's saved model choices carry
   over without an edit.

## Consequences

- **Breaking.** `/acs:create-design` is gone. A team or script that invoked it
  invokes `/acs:create-tech-design`; the gate, the inputs and the loop are the
  same. Saved settings migrate on their own; nothing else needs to be run.
- The hand-off no longer carries its own architecture section. A change whose
  interfaces, data or flows are not designed yet shows "none yet" in `## LLD`
  and the skill to run, instead of a second, unversioned copy of that design.
- A team can see, and record, that it accepted a design before implementation
  started: the approver record (`status_by`, `status_at`, `status_reason`) sits
  in the document. Approval is advisory to `/acs:create-impl-plan`, as plan
  approval is to the delivery paths that do not enforce it.
- `design.md` files and `steps/create-design/` folders from earlier runs stay
  valid inputs. `design list` does not list a legacy `design.md`, which carries
  no version block to move.
- History keeps the old name: earlier ADRs, released CHANGELOG sections and dated
  notes say `create-design`, because that is what the skill was called when they
  were written. The clarification ledger's skill enum keeps `create-design` beside
  the new name so an old ledger still validates.
- No new agent file and no new skill: 29 skills, 34 agent files.
