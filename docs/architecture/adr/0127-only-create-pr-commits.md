# 0127 — Only `/acs:create-pr` branches, commits and pushes

**Status**: Accepted · **Date**: 2026-10-04

**Amends**: [0090](0090-ticket-artifacts-in-repo-docs-tree.md) (who commits the
ticket's documents, and when), [0114](0114-analyze-requirements-controller-driven-loop.md)
(analyze-requirements' publish no longer commits), [0110](0110-parallel-fan-out-and-parallel-groups.md)
(parallel writers no longer commit, so there is no `index.lock` to wait on),
[0126](0126-lld-data-design-and-flows.md) (its "documents stay local" becomes the rule
for every skill, and its exception for the analysis publish goes).

## Context

Git writes were spread across the pipeline. `/acs:analyze-requirements`' publish
committed the ticket's docs folder on the ticket branch, `/acs:create-impl-plan`,
`/acs:create-api-contract` and `/acs:create-test-docs` each committed their document,
every `/acs:code` implementer committed its partition, `/acs:docs-sync` and
`/acs:create-e2e-tests` committed their files, and `/acs:create-prd` and
`/acs:create-architecture` each minted a delivery ticket, cut a branch, committed and
opened their own docs-only PR. `/acs:create-pr` only pushed what the others had left.

That had three costs. The history a reviewer read was whatever order the steps
happened to run in — a plan commit between two code commits, a fix commit on top of a
review — rather than something shaped for review. Every writer had to know which
branch it was on, refuse the default branch, and retry git's `index.lock` when a
sibling committed at the same moment. And a user who wanted to look at a step's
output before it entered the history had no way to: the step had already committed it.
ADR-0126 already left the low-level design documents as local changes for the user to
commit; the rest of the pipeline did not follow.

## Decision

1. **No acs skill creates or switches a branch, stages, commits or pushes — except
   `/acs:create-pr`.** Every other skill leaves its output as uncommitted changes in
   the working tree, on whatever branch is checked out, and records every path it wrote,
   repo-relative, in its result's `states.files` (implementers in their reports'
   `files_changed`). Two exceptions stay: `/acs:release` keeps its own `release/*`
   version-bump PR (ADR-0052), and `/acs:merge-pr` keeps the merge and its post-merge
   cleanup (delete the merged branch, check out the base, pull).
2. **`/acs:create-pr` splits the changes into small reviewable commits**, layer by
   layer and slice by slice, and shows the split as a **preview the user confirms**
   before anything is committed: the ticket's documents (`docs/tickets/<ID>/`); the
   design documents (`hld/`, `lld/<feature>/`, ADRs from `/acs:create-design`); then
   per plan slice or file-map partition its tests, then its code (one commit when a
   slice has only one kind); then `/acs:docs-sync`'s updates; then the e2e suites.
   A file changed since the run began that no step recorded is **left out and listed**
   (the user may add it to a group); a file that was already dirty when the run began
   is never included unless a step recorded it. Paths are always staged by name —
   never `git add -A` or `git add .`.
3. **Every change, docs or code, goes through `/acs:create-pr`, which takes a ticket
   id or a prompt.** There is no separate docs mode. With no argument it continues this
   checkout's current run, whatever its subject. With a prompt and no current run it
   opens a prompt-subject run whose changeset is every uncommitted change against
   HEAD, grouped by layer — documents by doc set (the PRD, `hld/`, each
   `lld/<feature>/`, the ADRs, the ticket docs), then tests, then code — using the
   paths other runs recorded in `states.files` to place each file. The
   `verifier_passed` brake applies only when the run has a code step, and a commit
   subject names a ticket only when there is one. `/acs:create-prd` and
   `/acs:create-architecture` no longer mint a delivery ticket, branch, commit or open
   a PR: they run ticketless, the way the audits do (ADR-0123), leave their documents
   local as `/acs:create-data-design` and `/acs:create-flows` do (ADR-0126), and point
   at `/acs:create-pr "<what changed>"`.
4. **`/acs:analyze-requirements`' publish writes, it does not commit.** It writes the
   ticket's docs folder into the working tree and records the paths; the verification
   reads the working-tree bytes instead of `git show HEAD:`.

**The mechanics** live in `acs_lib.changes`, `acs_lib.commit_plan` and the CLI:

- **Baseline.** The first `acs.py step start` of a run writes `<run>/baseline.json`
  once and never overwrites it: the HEAD the run started from, the branch, and every
  path already dirty or untracked at that moment with its blob id. Ticketless runs
  record one too. Those paths are left out of the run's changeset — someone else's
  work in progress — except when the run's first step reads existing work
  (review-code, docs-sync, create-pr, run-e2e-tests): then the hand-written changes
  are its subject, and the baseline records `adopts_dirty`.
- **Snapshot.** `acs.py changes snapshot` returns a git tree id of the whole working
  tree, untracked non-ignored files included, built in a throwaway index so the real
  index and the tree are never touched. `/acs:review-code` records it as the verdict's
  `reviewed_sha` (the field keeps its name; it now names a tree, not a commit), and
  `/acs:code` asks "what changed since the review" with `changes diff --since
  <reviewed_sha>`.
- **Changeset.** `acs.py changes diff [--since <tree-or-commit>] [--name-only|--stat|
  --patch]` diffs `<since>` (default: the baseline's HEAD) against a fresh snapshot,
  leaving out the baseline's dirty paths unless they changed again. It replaces every
  `git diff <default>...HEAD` and `git log <branch>` read of "this run's changes".
- **Commit plan.** `acs.py pr plan-commits [--ticket ID] [--run R]` builds the groups
  deterministically — from the run's recorded results intersected with the changeset
  when its steps recorded what they wrote, else from every uncommitted change grouped
  by layer —
  `{branch, base, groups: [{id, subject, layer, paths}], left_out, excluded}` — and
  `acs.py pr commit --plan <file>` executes a plan the user may have edited: it switches
  to the branch when not already on it (carrying the working tree), then stages and
  commits each group by pathspec, refusing a path outside the changeset, an empty group
  and a branch named like the default. It never pushes; `/acs:create-pr` pushes.

## Consequences

- The PR history is shaped for review — documents, then each slice's tests and code —
  and the user sees, and can edit, the split before it exists.
- No writer needs to know its branch, refuse the default branch or retry
  `index.lock`; parallel writers join on their reports and the file-map guard. The
  sibling-judge rule in `/acs:ship` becomes "after every sibling writer has written".
- The delivery-ticket path goes: `DELIVERY_TICKET_SKILLS` is empty, `step start
  --allocate` stays for `/acs:create-ticket` only, and the shared delivery-PR reference
  `/acs:create-prd` and `/acs:create-architecture` followed is deleted. A PRD or HLD
  change no longer leaves a delivery ticket in the index.
- `/acs:create-pr`'s old "uncommitted changes → stop" rule inverts: uncommitted changes
  are its input.
- A follow-up makes every skill accept a prompt or a ticket id (no skill requires a
  ticket).
- **Limitation: one checkout, one working tree.** Two tickets in flight in the same
  checkout share one working tree, and so one changeset; the baseline keeps a file that
  was dirty before a run out of that run's commits, but it cannot tell two concurrent
  runs' new files apart. Work on concurrent tickets in a separate worktree each
  (`git worktree add`), which acs already treats as its own checkout.
- A ticket in flight across the upgrade keeps the commits its earlier steps already
  made on its branch; its baseline is recorded by its next `acs.py step start`, so
  only what changes after that is grouped into new commits.
