# 0090 — Ticket and design artifacts live in the repo docs tree; the workspace keeps the run ledger

**Status**: Accepted · **Date**: 2026-09-12

## Context

ADR-0003 put every pipeline artifact in a workspace outside the repo;
ADR-0086 superseded its location, moving that workspace in-repo to
`.acs/state-machine/` (gitignored) so it is easy to find and shared across
worktrees. Neither decision distinguished between two very different kinds of
file that both ended up in `<workspace>/<repo>/<ticket-id>/`:

- **Run ledger** — `<skill>-state.json`, `pipeline-state.json`,
  `phases/<skill>/` artifacts, verdicts, `.lock`, `lock-events.jsonl`,
  `clarifications.json`, and the repo-level index/counters/metrics. Machine
  state, written by hooks, read by hooks, meaningless in a code review.
- **Ticket documents** — `ticket.json` and `design.md` then; `plan.md`
  (under `phases/code/`) since MAR-70. Human-facing: the statement of what is
  being built, why, and how. Exactly the material a reviewer wants beside the
  diff.

Keeping the second group in a gitignored folder had three consequences worth
the price of a decision:

- **The reasoning never reached the PR.** A reviewer saw the code and the PR
  body; the ticket's acceptance criteria and the design that justified the
  approach sat on one machine, in a folder git was told to ignore.
- **It was not versioned.** A design that changed mid-ticket left no diff.
  The audit trail was append-only *runs*, never an editable document's
  history.
- **`status` had two homes.** `ticket.json.status` was maintained by hooks
  alongside `pipeline-state.json`'s step ledger — two records of the same
  fact, with a documented rule that gates read the ledger and never
  `ticket.status`, which is what one writes when two records have already
  disagreed once.

Options weighed:

- **Status quo plus a PR-body summary.** Cheapest, and it is what the PR
  template already approximates; it makes the summary reviewable but not the
  document, and leaves `status` duplicated.
- **Mirror the documents into the repo on every write.** Reviewable, but two
  copies with a sync step is the problem, restated.
- **Move the human-facing documents into the repo docs tree and leave the
  ledger in the workspace (chosen).** One home each, split by audience.

## Decision

**A ticket's human-facing documents live in the consumer repo** at
`<repo>/<settings.artifacts.tickets_path>/<ID>/`, default
`docs/tickets/<ID>/`: `ticket.md`, `design.md`, `analysis.md`,
`api-contract.md`, `plan.md`, `test-cases.md`. They are committed on the
ticket branch and reviewed in the PR like any other doc. **The workspace
keeps the run ledger**, unchanged in shape and location (ADR-0086 stands).

**`ticket.md` is markdown with YAML front matter** carrying every field
`ticket.json` carried **except `status`**, plus `## Description`,
`## Acceptance criteria` (a numbered list) and `## Clarifications` — the last
a read-only mirror rendered from `clarifications.json`, which remains the
ledger's own append-only record. The front matter is written and read by the
same strict YAML subset the workflow files use, so the plugin gains no
dependency for this.

**`status` is derived, never stored.** `derive_status(tdir)` reads the ledger:
`done` when the partition is archived, `steps.merge-pr` is completed, or (for
an epic) every child is done; `in_review` when `steps.create-pr` is completed
or a delivery skill recorded a PR; `in_progress` when any step other than
`create-ticket` has a status other than `skipped`; `open` otherwise.
`load_ticket()` still returns `status` in its dict, so no caller changes —
the field simply can no longer disagree with the ledger, because there is
nothing left to disagree with.

**Opting out is a first-class setting, not a fork.**
`artifacts.tickets_path: null` keeps every document in the workspace
partition exactly as before. Every reader resolves a document by looking in
the docs tree first and the partition second, so **a repo that never migrates
keeps working**: `load_ticket` reads `ticket.md`, else `ticket.json`, else
the `ticket.json.moved` pointer.

**Migration is explicit, idempotent, and one-way.**
`acs.py artifacts migrate [--dry-run]` renders each live partition's
`ticket.json` to `docs/tickets/<ID>/ticket.md`, copies `design.md` and
`phases/code/plan.md` beside it when nothing is already there, writes
`<partition>/ticket.json.moved` naming the new path, and unlinks
`ticket.json`. Archived partitions are never migrated — a done ticket's
history is not worth rewriting. It refuses while a partition it still has to
move holds a `.lock`, and it refuses outright when `tickets_path` is `null`.

**The docs tree is a control input to the file-map guard.** An executor
subagent's write anywhere under `<tickets_path>/` is denied with exit 2 and a
message naming it as a control input only the coordinator and the ticket
skills write. The reasoning is the same one that already protects the guard's
own inputs: an executor that can edit the ticket can widen its own scope, and
an approval that the thing being approved can rewrite is not an approval.

**`contracts_path` (default `docs/api`) is introduced by the same decision**
for the repo-level, machine-readable contract files `/acs:create-api-contract`
maintains; `null` means the ticket folder only. It is a separate key because
those files are the *repo's* API surface, not one ticket's document, and
outlive the ticket.

## Consequences

**Positive.** The ticket, its design, its plan and its test cases arrive in
the PR with the diff they justify, so a reviewer can check the change against
its own stated intent without leaving the review. They are versioned: a
mid-ticket design change is a diff with an author and a date, which the
append-only `runs` array never gave. `status` has one source. And the split
is legible — "is this for a person or for a hook?" decides where a new
artifact goes, which is a rule an author can apply without asking.

**Accepted cost: ticket documents are now part of the repo's history,
permanently.** A clarification recorded in a ticket, a rejected design
option, an estimate — all of it is public in the repo forever, on the same
terms as the code. For an open-source consumer that is a disclosure decision,
not a neutral one, which is why `artifacts.tickets_path: null` exists and is
documented as a supported configuration rather than a legacy mode.

**Accepted cost: the tree grows.** One folder per ticket, never pruned by
acs — a repo that ships a thousand tickets has a thousand folders. Archiving
moves the *partition*, not the documents, deliberately: the point of putting
them in the repo was that they stay with the code they describe.

**Behaviour change, not merely relocation.** A skill that previously wrote
`design.md` into the partition now writes it into a **tracked** directory, so
its output lands in a commit and, if the branch is pushed, in a PR. Skills
that write there must therefore be branch-aware in a way they did not have to
be before.

**Known limitation, accepted.** `migrate` is one-way: there is no
`unmigrate`. Setting `tickets_path` back to `null` after migrating makes the
readers fall back to a partition whose `ticket.json` is gone, leaving the
`ticket.json.moved` pointer as the only path back to the document. That is
recorded rather than fixed because the reverse move has no user we could
name, and an unused reverse migration is a second code path to keep correct.
