# 0102 — Documents are found, not configured: no path settings

**Status**: Accepted · **Date**: 2026-09-23

**Amends**: [0086](0086-in-repo-anchored-state-machine.md) (the in-repo
workspace stands; its `workspace_path` override is removed),
[0090](0090-ticket-artifacts-in-repo-docs-tree.md) (ticket documents stay in
`docs/tickets/<ID>/`; the `artifacts.tickets_path` setting and its `null`
opt-out are removed), [0094](0094-doc-set-legs-fold-into-create-docs.md)
(`DOC_SETS` rows carry a default directory instead of a settings key),
[0101](0101-gating-skills-that-are-not-workflow-steps.md) (`ARCHITECTURE_GATED`
and `PRD_GATED` are removed; `SUBJECT_GATES` is the one table left)

## Context

acs told every skill where a repo's documents live through settings: twelve
keys (`prd_path`, `architecture_path`, `requirements_path`,
`requirements_layout`, `adr_path`, `quality_path`, `operations_path`,
`principles_path`, `standards_path`, `artifacts.tickets_path`,
`contracts_path`, `workspace_path`), each with a default that nearly every
repo kept. Their readers were spread across 36 skill and agent files and a
handful of hook modules, and `/acs:setup` asked about them.

Claude Code already has a way for a session to learn where things are in a
repo. `CLAUDE.md` is loaded into every session as project instructions, and
an agent follows it, and whatever docs index it points at, only as far as the
task needs. A path setting is a second copy of that knowledge, kept in a place
the rest of the session never reads. It also goes stale silently: a PRD moved
by hand is still "at" `docs/product` as far as the setting knows.

## Decision

**1 · No setting locates a document.** The twelve keys are removed from the
settings schema, `DEFAULT_SETTINGS`, `/acs:setup` and every reader. A skill
finds a document the way any session does: through `CLAUDE.md`, any docs index
the repo keeps, and then a search. If it finds none, it creates the document
at a conventional default: `docs/product/`, `docs/architecture/`,
`docs/requirements/` (with `functional/` and `non-functional/`), `docs/adr/`,
`docs/quality/`, `docs/operations/`, `docs/principles/`, `docs/standards/` or
`docs/api/`. A coordinator resolves locations once at Start and passes them to
its subagents as task constraints.

**2 · What the hooks own stays fixed.** The hooks read and guard two locations
without asking anyone, so those two are constants, not discoveries:

- ticket documents live at `docs/tickets/<ID>/`, given by
  `acs_lib.artifacts.TICKETS_PATH`;
- the workspace is `<main-checkout>/.acs/state-machine`, given by
  `default_state_root`.

A bare repository, a submodule or an unusual git layout has no override any
more. acs must be run from a regular checkout.

**3 · Document preconditions move from hooks into skills.** The pre-hook
checked for `prd.md` before `/acs:create-architecture`, and for
`hld/tech-stack.md` before `/acs:create-project`, `/acs:standardize-project`
and `/acs:create-docs`, in each case at the configured path. A hook cannot
find a document that has no configured path, so these checks now run in the
skills themselves, at Start, and refuse with the same messages.
`SUBJECT_GATES` still runs in the hook, because it gates state acs owns.

**4 · `fanout_batches` takes the coordinator's findings.** Deciding whether a
doc set is "already in the repo" is now discovery work. The coordinator
reports the sets it found (`present`). `fanout_batches(tickets_index,
candidates, present)` stays the deterministic half: eligibility and batching.
`doc_set_present_on_disk` is removed.

## Consequences

**Existing settings keep validating.** The schema tolerates unknown keys, so a
consumer's `prd_path` or `workspace_path` is now simply ignored. There is one
real behaviour change. A repo whose `workspace_path` pointed outside the
checkout now reads its state from `.acs/state-machine`, so its runs must be
moved with `migrate_workspace.py` (ADR-0086's migrator).

**Opt-outs expressed as `null` are gone.** These are `tickets_path: null`
(ticket documents stay in the partition), `adr_path: null` (no ADR commits)
and `contracts_path: null` (no repo-level contract files). The found-or-default
rule replaces them. A repo that wants no ADRs says so in its `CLAUDE.md`,
which is exactly the kind of instruction every session already reads.

**Less is checked deterministically.** Two refusals moved from a hook to a
skill's prose. That is weaker than a hook, and ADR-0001 prefers hooks. It is
accepted because the alternative is a hook refusing a repo whose PRD sits
somewhere the setting does not name, and that is the rigidity this decision
removes. Anything acs itself writes and later reads back is still found by a
constant.

**Out of scope.** The `release` block's file pointers (`changelog_path`,
`version_locations`, `extra_refs`, `publish_driver`) stay. A deterministic
release driver edits those exact files, so they are not documents an agent
discovers.
