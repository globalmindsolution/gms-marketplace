# /acs:merge-pr — the exempt non-ticket PR mode

Open this ONLY when the invocation carried `--pr <PRNUMBER>` (or `#N`, or a PR
URL), or when `acs step start` printed a context whose `mode` is `"exempt-pr"`.
A ticketed run never needs a line of it: the two paths share the readiness
command and the merge call, and everything below is about what the exempt path
does INSTEAD of a partition — which is nothing.

## Exempt non-ticket PR mode

`/acs:merge-pr --pr <PRNUMBER>` (also `#N` or a PR URL) merges a **legitimate
one-off non-ticket PR** — a hotfix, a chore, a doc tweak that never went
through the pipeline — without inventing a ticket for it. It is the sanctioned
counterpart to the convention-enforcement gate's `exempt_label` /
`exempt_branches` escape hatch: instead of a raw `gh pr merge` (which the gate
fights), the user labels the PR with the exempt label and merges it here. Like
the ticket path, it runs the same readiness brakes (including the
approved-review requirement) and branch-protection checks before merging;
/acs:ship never invokes it.

The Start step below already passes `--args "$ARGUMENTS"`; for the exempt form
the same command resolves the mode. Run it and read the printed context JSON:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step merge-pr --pr "<PRNUMBER>"
```

If `acs step start` exits non-zero (the PR is not OPEN, is a draft, is not a
sanctioned exempt PR, or is ticket-backed) STOP and surface its stderr
verbatim — including its `/acs:merge-pr <TICKET-ID>` redirect when the PR looks
ticket-backed. Do not improvise a workaround. On success it prints a context
JSON with `mode: "exempt-pr"`, the resolved `pr` (`number`, `url`, `branch`,
`base`, `labels`), `exempt_reason` and `settings` — and it resolves **no**
ticket and writes **no** partition, lock, pointer, or state.

When `mode` is `exempt-pr`, run this trimmed flow yourself (no
planner/executor/verifier subagents — there is no partition to persist phase
artifacts to):

1. **Readiness review** — the SAME command as the ticket path, so the two
   cannot disagree about the same PR:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" readiness --pr <pr.number>
   ```

   Dispatch on `verdict` exactly as the ticket path does. This is not a
   restatement of the four dimensions but the same decision table: when the
   rules moved into `acs.py readiness` (MAR-524) this path was left describing
   reads that no longer decide anything, so a `mergeable` of `UNKNOWN` failed
   on one path and passed on the other for the same PR. The command classifies
   its own gh failures — an unevaluable read exits 2 with gh's verbatim stderr
   and the canonical hint (ADR-0088), before any merge is attempted. A
   `blocked` verdict is the same REPORT-ONLY stop: do not merge, tell the user
   exactly what blocks, stop.
2. **Merge (only when all four pass, or after the BEHIND carve-out succeeds)**
   — when `mergeStateStatus == BEHIND` and all other three dimensions pass,
   apply the identical BEHIND carve-out as the ticket path (user-confirmed
   extension C-10): run `gh pr update-branch <pr.number>` (merge-update — no
   `--rebase`, no force-push), then poll `gh pr checks <pr.number> --required`
   at 15-second intervals for up to 5 minutes (same C-6/C-8 parameters as the
   ticket path — up to 2 total update-branch attempts). On conflict: REPORT-ONLY
   with `summary: "update-branch conflict — base cannot be merged into PR
   branch cleanly; resolve the conflict and re-invoke /acs:merge-pr"`. On
   poll timeout: REPORT-ONLY with `summary: "branch updated but required CI
   still running after 5 min — re-invoke /acs:merge-pr to merge once CI passes"`.
   On base advancing again beyond 2 attempts: REPORT-ONLY with `summary:
   "base advanced again after 2 update attempts — re-invoke /acs:merge-pr once
   the base stabilizes"`. When all four dimensions pass (or after a successful
   update-branch sub-flow), merge with the configured strategy and delete the
   remote branch:

   ```bash
   gh pr merge <pr.number> --<settings.merge_strategy> --delete-branch
   ```

   **Critical**, identically to the ticket path's Step 1: a non-zero exit is
   gh's verbatim stderr plus the canonical hint, then STOP — before the
   Cleanup step (3, below) ever runs, no retry, no fallback to any other
   transport. Never re-merge a PR `gh pr view` already reports `MERGED`.
3. **Cleanup** — from the main checkout (resolve it via
   `git rev-parse --git-common-dir`), remove the worktree if one holds
   `pr.branch` (`git worktree remove <path>`) and delete the local branch if it
   still exists (`git branch -D <pr.branch>`).

There is no post step: with no ticket there is nothing to record, and acs keeps
no repo-level metrics (ADR-0104).

**Explicitly NOT done in exempt mode** (there is no ticket): NO partition
artifacts (no phase files, no `result.json` — there is no partition), NO
tracker sync (no `ticket.external`), NO ticket archiving, NO ticket status
flip, NO epic auto-done. Contrast with the ticket path's
`post-merge-pr.py --ticket … --result-file …` (Finish, below). Report a compact
summary to the user — merged or blocked (per dimension), whether an
update-branch step was performed (when BEHIND), strategy used, branch and
worktree cleanup performed — then stop.
