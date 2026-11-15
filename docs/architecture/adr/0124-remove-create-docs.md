# 0124 — Remove `/acs:create-docs`: the quality, operations, principles and standards docs are hand-written

**Status**: Accepted · **Date**: 2026-10-04

**Supersedes**: [0094](0094-doc-set-legs-fold-into-create-docs.md) (the doc-set
fold into `/acs:create-docs`) and [0085](0085-doc-bootstrap-parallel-fan-out.md)
(its parallel fan-out).
**Amends**: [0011](0011-sdlc-doc-sets-quality-and-operations.md) (no skill
bootstraps the quality and operations sets),
[0012](0012-design-time-doc-consistency.md) (one carrier of the doc-consistency
step fewer), [0080](0080-plan-conformance-citation-corroboration-hybrid-mechanism.md)
(the doc-set author and reviewer it applied to are gone),
[0092](0092-skill-machinery-declared-per-skill.md) (class D's first skill is
gone) and [0118](0118-discovery-design-development-phases.md) (the Design phase
loses `/acs:create-docs`).

## Context

`/acs:create-docs` bootstrapped and maintained four product doc sets — quality
(test strategy, coverage policy), operations (release process, runbooks,
observability, incident response, test scheduling), principles and standards —
from templates shipped in the plugin, each set on its own delivery ticket and
docs-only PR. It carried a good deal of machinery for that: a `DOC_SETS` table
and its derived views in `acs_lib`, a fan-out helper and an argument parser,
the `acs fanout batches` command, a `doc_set` ticket field and the
`acs step start --doc-set` flag, an author and a reviewer agent, a pre/post
hook pair, four template directories, ten routing cases and seven behaviour
cases.

What the sets are for does not need that machinery. Nothing in the pipeline
reads a set because `/acs:create-docs` wrote it: `/acs:create-design`,
`/acs:create-impl-plan` and `/acs:review-code`'s craft lens find the standards
set wherever the repo keeps it (ADR-0102), and `/acs:docs-sync` brings a touched
runbook or guide in line with a change. The documents themselves are short,
specific to the team, and best written by the person who owns the policy they
state. The owner decided acs no longer needs the skill.

## Decision

1. **`/acs:create-docs` is removed**, with everything that existed only for it:
   the skill, `create-docs-author` and `create-docs-reviewer`, `pre-` and
   `post-create-docs.py`, `templates/{quality,operations,principles,standards}/`,
   `DOC_SETS` and its views, `fanout_batches` / `parse_doc_set_arg` /
   `parse_fanout_for_arg`, the `acs fanout batches` command, the `--doc-set`
   flag and the `doc_set` ticket field, its eval cases and its tests.
2. **The four doc sets are hand-written.** acs no longer creates them. The
   skills that read them keep finding them where they are, unchanged; an
   absent set stays "not applicable", never a block.
3. **What other skills need stays.** `citation_check.py` (imported by
   `prd_conformance_check.py`) and `structure_lint.py` stay. The test-scheduling
   recipe `/acs:run-e2e-tests` points at moves out of the operations template
   into that skill's own `references/test-scheduling.md`.
4. **Settings migrate.** `models.create-docs` names a skill that no longer
   ships, so `acs.py settings migrate --write` drops it, as it already drops the
   skills ADR-0118 removed; `validate_settings` names it until then.

## Consequences

- 26 skills, 27 agent files, 17 hooked skills with 17 pre/post hook pairs. Nine
  skills run a write → judge loop, all of them authoring skills.
- The Design phase is `create-prd`, `create-architecture`, `create-ticket` and
  `create-design`. The PRD's full-SDLC coverage goal (G33) no longer has an
  operating skill for the quality, operate and standards/principles phases: their
  documents are maintained by the named accountable role, and the skills that
  read them are their consumers.
- A consumer with an open `/acs:create-docs` delivery PR merges it by hand:
  `/acs:merge-pr` reads the recorded PR reference only from the delivery skills
  that still ship. Old tickets keep their `doc_set` field; nothing reads it.
- Clarification ledgers written by a create-docs run still validate: the
  ledger schema keeps the skill name, as it keeps the other removed skills'.
- Released CHANGELOG sections and the superseded ADRs keep describing the skill
  as it shipped; they are the record, not the current design.
