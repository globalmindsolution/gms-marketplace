# 0110 — Parallelism by default: sliced fan-out inside a skill, parallel groups in the workflow

**Status**: Accepted · **Date**: 2026-09-27

**Amends**: [0096](0096-workflow-is-a-list-not-a-graph.md) (a step entry may
now be a list of skill names, a parallel group; the list still carries no
conditions), [0109](0109-subagents-per-skill-logic-and-no-skill-manifest.md)
(each role still has one agent file; a coordinator may now run several
instances of it at once over disjoint work)

## Context

ADR-0109 gave every skill its own subagents, each named for its work. Most of
them still ran one at a time. Only `/acs:code` (one implementer per file-map
partition), `/acs:create-docs` (doc sets in capped parallel) and
`/acs:review-code` (five lenses, one adjudicator per finding) fanned out by
default. Everywhere else, parallel work was an optional "you MAY run two"
limited to remediation rounds. Meanwhile a coordinator waited on survey work
that splits cleanly by repo area, on judges running check dimensions that
share no state, on writers producing disjoint files, and in `/acs:ship` on
whole steps that follow the same reviewed changeset and write disjoint files.

Two host facts bound what is possible. A subagent cannot spawn a subagent, so
every fan-out is the coordinator's. And a step's coordinator runs in the
invoking session, so two workflow steps cannot each get a session of their
own inside one run.

## Decision

**1 · Sliced fan-out inside a skill.** A coordinator runs N instances of the
SAME agent in one message, each over a disjoint slice, capped at
`max_parallel = 4` per phase (a skill with its own cap keeps it). It applies
to three kinds of work:

- **Writers**, by default from iteration 1 whenever the deliverable splits
  into disjoint files: authors per feature area, architects per HLD/LLD,
  scaffolders per allowlist slice, test-writers per suite file, doc-updaters
  per doc area. Implementers per file-map partition, as before.
- **Judges**, by default when a judge has five or more check dimensions: the
  dimensions split into two or three named slices. Each deterministic checker
  runs in exactly one slice, and a judge that runs something once (a build, a
  suite) keeps that run in one slice.
- **Surveys**, when the scope spans two or more disjoint top-level areas of
  the repo. Every slice's open questions go into one grouped
  clarification-ledger ask.

Each instance carries `slice="<id>"` on its task and result. Its report is
`iter-<n>/<role>-<id>.*`, and its snapshot is
`iter-<n>/<role>-<id>-message.xml`, so siblings never overwrite each other.
The join is deterministic: `acs notes merge` merges the slices' markdown by
`## ` heading into the one file every downstream reader and checker expects
(`authoring.md`, `<role>.md`). A missing slice fails the merge. A sliced judge
passes only when every slice passed.

**Joining is not synthesizing.** The merge is enough only where slices
cannot disagree, as with judge slices, which own disjoint dimensions (the
coordinator also drops a finding another slice already raised at the same
location for the same defect). Where slices meet at a seam, the skill
reconciles them before the next phase:

- After parallel writers and before the judge, one more instance of the same
  writer role runs with `slice="integration"`. This generalises
  `/acs:code-complex`'s final integration implementer. It reconciles only
  the seams each skill names: shared terms and IDs, cross-references, index
  and overview files, shared fixtures and config. It records every seam it
  changed in `iter-<n>/<role>-integration.json`, returns a conflict it cannot
  settle from the evidence as a question, and is skipped when one writer ran.
- A single writer that consumes merged survey slices reconciles their
  contradictions under a `## Synthesis` section of its notes, with the
  resolution and its evidence or an open question. It never silently picks
  one.

**2 · Parallel groups in the workflow.** A `ship.yaml` step entry may be a
list of two or more skill names. Each entry is a stage. The members of a stage
may all be `in_progress` at once (invariant I1 now reads "one stage", not
"one step"), and `acs run next` reports them together in `due`. `/acs:ship`
invokes every member and advances their coordinators in lockstep in its own
session. It spawns each phase's subagents for all members in one message, asks
the user once for all members, and lets each member finish itself. A loop's
ends may not sit inside a group. The shipped workflow runs `create-e2e-tests`
and `docs-sync` as one group: both follow the reviewed changeset and write
disjoint files. A member whose judge re-derives from the branch diff
(`docs-sync`'s drift-reviewer) judges only after every sibling writer has
committed for the last time, so it judges the diff the group leaves behind.

The run ledger follows the group, not its first member. The run lock is
released by the last member to finish, since an earlier release would let a
second checkout in while a sibling is still writing. SessionEnd and a
handoff finalize every open member as `interrupted`, and a handoff with more
than one open member resumes through `/acs:ship`.

**3 · The write guard handles several writers.** With writers of different
skills live at once, a write is judged against its own writer's map when the
hook payload names the agent. A payload naming an agent that is not a live
writer (a judge or a surveyor) is not the guard's to scope. A payload naming
no agent is judged against the union of every live writer's scope, never
against whichever writer started last. In that union, a writer whose skill
declared no map contributes its own step directory and nothing more.

## Consequences

- Wall time falls wherever work splits. Token cost rises with sliced judges,
  which re-read shared inputs once per slice. The per-phase cap bounds it.
- Commits from parallel writers meet git's `index.lock`. The rule is wait and
  retry, never delete the lock.
- An unattributed write under several live writers is checked against their
  union, so a writer may touch a sibling skill's mapped file. A map-less
  writer's unattributed write outside its siblings' maps is denied and comes
  back as `needs_input`. On a Claude Code that sends `agent_id` on tool hooks
  the check is exact.
- A parallel group costs the coordinator's context: every member's
  coordinator prose is loaded together. Groups are declared, never derived,
  and the shipped workflow declares one.
