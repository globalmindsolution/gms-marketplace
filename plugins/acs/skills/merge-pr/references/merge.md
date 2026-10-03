# /acs:merge-pr — landing the PR and cleaning up (the Inline apply flow's charter)

Open this when the ticketed run reaches its Inline merge-pr apply flow in
SKILL.md, and follow it yourself. /acs:merge-pr spawns no subagent: merging a
ready PR and cleaning up after it is a fixed, ordered sequence of commands that
share state, with nothing for a separate agent to judge, so the coordinator
runs it inline. The readiness review (SKILL.md's Step 0) decides whether a
merge happens at all; this file is how it happens once it does: merge the PR
with the configured strategy, then perform the post-merge cleanup, in order,
recording every command and its outcome. Nothing here makes an unready PR
mergeable: no pushing commits, no resolving conflicts, no dismissing reviews,
no editing the PR.

**Where the cross-references below point.** Step numbers are the Inline
merge-pr apply flow's in SKILL.md (Step 0 readiness, Step 1a the BEHIND
carve-out, Step 1 merge, Step 2 cleanup), which states each in full. The
exempt `--pr` path is `references/exempt-pr-mode.md` and runs its own trimmed
flow — nothing below applies to it.

## What you work from

Read these yourself before running anything — workspace state, never
conversation history:

- the PR-bearing state file's `states.pr` = `{number, url, branch, base}`
  (`steps/create-pr/state.json`, or the delivery-ticket skill's
  `steps/<skill>/state.json` for a product-level ticket);
- `<partition>/ticket.json` — `ticket.external` drives the tracker step;
- `settings.merge_strategy` (`squash`|`merge`|`rebase`) and
  `settings.tracker.provider` (`local`|`github`);
- the cleanup inventory Step 0 took: the local branch, the worktree holding
  it, whether a tracker transition is needed.

## GitHub call failure policy, as it applies here

Canon lives in `merge-pr/SKILL.md`'s own "GitHub call failure policy"
section — this reference classifies no `gh` call itself, it only follows that
classification: critical for the merge itself and every readiness/
update-branch read (step 0, step 1a, step 1); loud-but-non-reverting for
Step 2's post-merge tracker sync only. Canon hint text
(`acs_lib.GH_ACCESS_HINT`, selected by `acs_lib.gh_failure_hint(stderr)`):

> This looks like a session-level access restriction — a Claude Code
> cloud/managed session must have the Claude GitHub App connected for this
> organization by an org admin. A local Claude Code session uses your own
> `gh` authentication and should not see this.

## Doing the work — strictly in this order

Run EVERYTHING from the main checkout (resolve it with
`git rev-parse --git-common-dir`) — never from inside the worktree you are
about to remove.

0. **Confirm state first**: `gh pr view <number> --json state,mergedAt`. If it
   already reports `MERGED` (normal on a resumed run), SKIP the readiness
   review, step 1a and step 1 entirely — never re-attempt a merge — and redo
   only the cleanup steps still outstanding. Otherwise run SKILL.md's Step 0
   readiness review and act on its `verdict`: `ready` → step 1,
   `update-branch` → step 1a, `blocked` → REPORT-ONLY stop.

1a. **Update branch (ONLY when `mergeStateStatus == BEHIND` at step 0 —
    SKIP this step entirely if `mergeStateStatus != BEHIND`)** — run:

    ```bash
    gh pr update-branch <number>
    ```

    (merge-update; no `--rebase`; no `--force`; no force-push). If exit
    non-zero (conflict detected): STOP with
    `summary: "update-branch conflict — base cannot be merged into PR
    branch cleanly; resolve the conflict and re-invoke /acs:merge-pr"`. Do NOT
    push fix commits; do NOT amend the PR; do NOT force-resolve the conflict.
    If exit 0: poll `gh pr checks <number> --required` at 15-second intervals
    for up to 5 minutes:
    - All required checks pass AND `mergeStateStatus != BEHIND` → proceed to
      step 1 (merge).
    - `mergeStateStatus == BEHIND` again (base advanced mid-poll) → re-run
      step 1a if total update-branch attempts < 2 (C-8); else STOP with
      `summary: "base advanced again after 2 update attempts
      — re-invoke /acs:merge-pr once the base stabilizes"`.
    - Poll timeout (5 minutes elapsed, no resolution) → STOP with
      `summary: "branch updated but required CI still running
      after 5 min — re-invoke /acs:merge-pr to merge once CI passes"`.

1. **Merge** with the configured strategy; `--delete-branch` removes the
   remote branch:

   ```bash
   gh pr merge <number> --<settings.merge_strategy> --delete-branch
   ```

   **Critical**: if GitHub rejects the command (the repo disallows the
   configured strategy, or the PR became unmergeable since the readiness
   review), record the exact gh stderr plus the canonical hint from
   `acs_lib.gh_failure_hint` and STOP, before any cleanup, per
   merge-pr/SKILL.md's classification — no fallback to any other transport.
   NEVER substitute another strategy, never retry with `--admin`.
2. **Remove the ticket worktree** when the inventory lists one:
   `git worktree remove <path>`. Append `--force` ONLY if leftover untracked
   files block removal AND step 0/1 confirmed the PR is merged. If the
   worktree holds uncommitted tracked changes, do not force — ask the user
   whether to discard them (SKILL.md's User interaction).
3. **Delete the local branch** if `git branch --list <pr.branch>` is
   non-empty: `git branch -D <pr.branch>`. If the branch is checked out in the
   main checkout, first `git checkout <pr.base> && git pull`.
4. **Sync the tracker to Done** — only when `settings.tracker.provider` !=
   `local` AND `ticket.external` is set. **Loud-but-non-reverting** (mirrors
   merge-pr/SKILL.md's Step 2 rule): the merge already landed at step 1 and
   is never revisited because of this step — a failed `gh issue close` or
   `gh project item-edit` here never reverts the merge and is never
   re-attempted automatically; record one error-severity finding naming the
   outstanding sync plus a replayable command block, and still report
   `merged_this_iteration` truthfully (the merge itself succeeded):
   - `github`: `gh issue close <external.key> --comment "Merged {ticket_id} via
     PR #{pr.number} — {pr.url}"`; when `tracker.github.project_number` is
     configured, also set the project's Status field to Done — locate the item
     with `gh project item-list <project_number> --owner <owner> --format json`,
     then `gh project item-edit --id <item-id> --project-id <project-id>
     --field-id <status-field-id> --single-select-option-id <done-option-id>`.
5. **Touch NOTHING else.** Do not edit `ticket.json` status, do not archive
   the partition, do not mark the parent epic done — `post-merge-pr.py` owns
   all of that; duplicating it corrupts workspace state.

## The merge report

Write `steps/merge-pr/iter-<n>/merge.json` recording: `pr`
(number/url/branch/base), `merged_this_iteration` (false when step 0 found it
already merged), `commands` — every command run, in order, with exit code and
trimmed output — `steps_skipped` (each with why: not applicable / already
done), and `problems`. The result document (SKILL.md's Finish) summarizes this
file; it never inlines the detail.

How the run ends, and what the report then says:

- **completed** — every applicable step done (merge plus all cleanup).
- **needs user input** — a destructive choice you must not make alone
  (dirty worktree, a branch holding commits absent from the merged PR); ask
  one question per point; the report records what already succeeded.
- **failed** — a step failed and you stopped (merge rejected, update-branch
  conflict, CI poll timeout): exact command + stderr in `problems` and the
  result document's `errors`, completed steps in the report, the summary
  naming the first failed step. Partial progress is normal and valuable — the
  report lets a resumed run redo only what failed. A failed step-4 tracker
  sync is NOT this case: the merge stands and the run still finishes with
  `merged: true`.

## Hard rules

- Spawn no subagent: the coordinator runs these steps itself, in one session,
  because they are ordered and share state.
- Mutate ONLY what this flow covers: the PR's merge state via `gh pr merge`,
  the remote branch (via `--delete-branch`), the local branch, the ticket
  worktree, the remote tracker item, and your own merge report (plus the
  result document and post-hook at Finish). Never another branch, never
  another PR, never repo files, never other workspace state.
- Follow this order exactly; a step this file does not list is a deviation —
  stop and record it in `problems`, never a silent extra fix.
- A readiness regression discovered mid-run (e.g. merge rejected because CI
  turned red) is REPORT-ONLY: stop and report it; never push fixes to the
  branch, never amend the PR to make it mergeable.
- **Exception — BEHIND-only update-branch:** `gh pr update-branch <number>`
  (merge-update; no `--rebase`; no force-push) is permitted SOLELY when step 0
  confirms `mergeStateStatus == BEHIND` AND the readiness verdict is
  `update-branch` (i.e., all other readiness dimensions passed). This is the
  ONE sanctioned branch mutation. No other branch push, amend, or force-push is
  ever permitted. An update-branch conflict or CI-timeout is REPORT-ONLY — do
  NOT force-resolve the conflict or push fix commits; stop with the
  appropriate summary (see step 1a above).

## Grounding (anti-hallucination)

Every decision, claim, and finding you record must be traceable to a source
you actually read or ran in THIS run:

- **Cite the source next to the statement it supports** in the merge report:
  file path with line numbers or section heading for anything based on repo
  code, docs, the ticket, or workspace state.
- **Quote the exact command and the relevant output** for anything based on a
  command run (git/gh state, the readiness JSON).
- **Never assert what you did not observe**: a merge `gh pr view` did not
  report, a check you did not see pass, a worktree you did not list. If an
  input is missing or unreadable, record it in `problems` instead of working
  from an assumed version.
- **Mark unverifiable points as assumptions**, with the reason the assumption
  is needed — an assumption is a finding to resolve with the user, never a
  silent default acted on.
