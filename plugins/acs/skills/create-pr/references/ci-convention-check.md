# /acs:create-pr — reading a red convention check before believing it

Open this when the "Branch / PR / commit conventions" check reports failing
after the PR is open. That check fails a PR whose description names no ticket
(ADR-0106). A run whose check comes back green never needs this file, and
a run that acts on a red one WITHOUT it is likely to act on a stale result:
the check reads a webhook payload frozen at the triggering event, so a
description or label fixed a moment later is invisible to the run that fired
before it.

Open it also when step 1's stacked-base pre-flight exits 1 — the last section
carries that remedy, which applies before the PR is ever opened.

**Where the cross-references below point.** The `gh run list` read this
section governs is classified as non-critical by SKILL.md's "GitHub call
failure policy"; the rule below is the one thing that policy does not cover.

### CI convention-check troubleshooting (frozen-payload gotcha)

`.github/workflows/acs-conventions.yml` reads `ACS_PR_BODY`, `ACS_PR_BRANCH`,
and `ACS_PR_LABELS` from `github.event.pull_request.*` in its `env:` block —
the webhook payload as it was FROZEN at the moment that specific triggering
event fired, never a live `gh pr view`/API call. A body or label change
applied via a separate call AFTER a given event fired is invisible to that
event's own check run; only a later event (its own
`edited`/`labeled`/`synchronize` run) observes it.

Re-running a completed workflow run (e.g. `rerun_workflow_run`) replays that
run's ORIGINAL frozen payload — it can never pick up a body or label change
made afterward. Rerunning an `opened`-triggered run that failed because the
description named no ticket will fail again every time, no matter how many
times it's rerun. Worse, if that rerun finishes AFTER a separate,
correctly-passing run (e.g. the `edited` run), its stale failing conclusion
can become the "latest" one GitHub reports for the check, shadowing the real,
already-green result. **Never treat a rerun of a stale/superseded run as a valid re-check.**

Before treating a failing "Branch / PR / commit conventions" check as real:

1. List the workflow runs for the PR's head SHA
   (`gh run list --branch <head-ref> --commit <head-sha>`), ordered by
   recency. This is a **non-critical** read: on failure, one `info` finding
   plus a replayable `gh run list --branch <head-ref> --commit <head-sha>`
   block, never abort — but the convention check itself is then reported
   **unverified, never assumed green**, since the newest run's conclusion
   could not be confirmed.
2. Read the NEWEST run's conclusion — that is the check's actual current
   state, regardless of what any older run for the same SHA reported.
3. If the newest run is already green, the check is fine; no action needed.
4. If a genuine re-check is needed (e.g. the payload really was wrong and a
   fix has since landed), trigger a FRESH webhook event rather than rerunning
   an old one — toggle a label off and back on (the workflow's `labeled`/
   `unlabeled` trigger types already listen for this), or push a new commit.
   Never call `rerun_workflow_run` on a stale/superseded run as the fix.

### A branch stacked on a squash-merged base (the step-1 pre-flight)

CI no longer reads commit subjects (ADR-0106), so this condition does not turn
the "Branch / PR / commit conventions" check red. Its subjects fail
`formats.commit_message`, and the author cannot fix them by renaming anything —
the local `pre-push` hook, when its `commit_message` check is on, refuses them.
It is caught before the push by step 1's pre-flight,
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/stacked-base.py" check`, so the
usual sighting is that report.

**The condition.** The pre-flight lists the branch's commits with
`git log --no-merges origin/<base>..HEAD` — pure SHA ancestry. A squash merge
replaces the base PR's commits with ONE new commit, so the originals never
become ancestors of the base. A branch stacked on that base still carries them,
the range still lists them, and the `commit_message` check fails on subjects
belonging to a pull request that is already merged.

**What the pre-flight reports.** One of three exits: `0` for verdict `clean` or
`own_violations` (nothing is stacked) and `1` for verdict `stacked_base`, each
printing one compact JSON object on stdout; and `2` when the condition cannot be
evaluated at all, which prints nothing on stdout and reports its reason on
stderr alone (`acs stacked-base: <reason>` — an unresolvable base ref, or no
merge base). Exit 2 is advisory: the run continues. On exit 1 the report's
`message` is the deliverable — it names the offending subjects with their short
SHAs and carries the replay command with real values substituted.

**On exit 0, read `notes` before concluding the subjects are yours.** That
conclusion holds while `notes` is empty: a non-conforming subject is then this
branch's own and gets the ordinary gate failure, never replay advice. A
NON-empty `notes` means the run qualified its own report — a commit it could
not test, an index it could not build, or absorbed-looking content with no safe
replay point — and `message` says which. A qualified exit 0 is not evidence of
ownership; it is the same kind of answer as exit 2, and the report's `message`
is what to record and carry on from.

**The remedy is a replay, not a rename.** The generic form is
`git rebase --onto origin/<base> <old-base>`; the report emits it with the
values filled in:

```bash
git fetch origin <base>
git rebase --onto origin/<base> <old-base>
git push --force-with-lease
```

`<old-base>` is the report's `replay_onto` — the tip of the branch that was
squashed. It is never guessed: the detector only ever names a commit whose
CUMULATIVE diff from the merge base reverse-applies to the base tree, which is
what makes everything up to and including it provably present in the base, so
replaying past it loses nothing. Every commit SHA on the branch changes when you
replay it, so any SHA recorded elsewhere — ticket partition phase artifacts,
`result.json` `commits` lists, PR or issue comments — is stale afterwards and
has to be updated by hand. /acs:create-pr never runs the rebase or the
force-push for you.

**What it will and will not tell you.** Only commits whose subject already fails
the `commit_message` format are examined, and a commit whose region the base
edited again after the squash is not recognised — a miss simply degrades to
today's behaviour, a red gate with no replay advice, never to a false alarm. In
the other direction one case is accepted deliberately: a branch whose entire net
content against the base is already in the base is reported as stacked even when
it was never stacked. The diagnosis is wrong there, but such a branch has no net
content, so the replay is a no-op and cannot lose work. A third case belongs to
degraded runs alone, and the report announces it rather than hiding it: with the
fork-point index unusable the check loses the control that tells a revert from
an inherited commit, so a commit that reverts this branch's own earlier work can
read as absorbed — the commit it reverted is unaffected. `notes` names the index
that failed and `message` carries the same warning, on either verdict.

**Do not reach for `git log --cherry-pick`.** Measured against the real
pre-replay branch (PR #562 stacked on PR #561, squash-merged as `d09c52f`),
`--cherry-pick --right-only` returned the SAME three non-conforming subjects as
plain ancestry: it matches by patch-id, per commit, and a squash merge produces
one combined patch whose patch-id matches none of the commits it replaced. The
GitHub API is no better — it derives a PR's commit list from the merge base,
which a squash does not move. No patch-id based detection can work here, and
none is implemented.

**This is a report, not a policy change.** Stacking a branch on an open PR stays
permitted, and the repository's merge strategy is unchanged — squash merges are
still how PRs land, which is why this condition exists at all.
