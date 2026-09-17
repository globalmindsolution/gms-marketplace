# /acs:create-pr — reading a red convention check before believing it

Open this when the "Branch / PR / commit conventions" check reports failing
after the PR is open. A run whose check comes back green never needs it, and
a run that acts on a red one WITHOUT it is likely to act on a stale result:
the check reads a webhook payload frozen at the triggering event, so a label
or title fixed a moment later is invisible to the run that fired before it.

**Where the cross-references below point.** The `gh run list` read this
section governs is classified as non-critical by SKILL.md's "GitHub call
failure policy"; the rule below is the one thing that policy does not cover.

### CI convention-check troubleshooting (frozen-payload gotcha)

`.github/workflows/acs-conventions.yml` reads `ACS_PR_TITLE`, `ACS_PR_BODY`,
`ACS_PR_BRANCH`, `ACS_BASE_REF`, and `ACS_PR_LABELS` from
`github.event.pull_request.*` in its `env:` block — the webhook payload as it
was FROZEN at the moment that specific triggering event fired, never a live
`gh pr view`/API call. A label, title, or body change applied via a separate
call AFTER a given event fired is invisible to that event's own check run;
only a later event (its own `edited`/`labeled`/`synchronize` run) observes it.

Re-running a completed workflow run (e.g. `rerun_workflow_run`) replays that
run's ORIGINAL frozen payload — it can never pick up a label, title, or body
change made afterward. Rerunning an `opened`-triggered run that failed for
missing-label reasons will fail again every time, no matter how many times
it's rerun. Worse, if that rerun finishes AFTER a separate, correctly-passing
run (e.g. the `labeled` run), its stale failing conclusion can become the
"latest" one GitHub reports for the check, shadowing the real, already-green
result. **Never treat a rerun of a stale/superseded run as a valid re-check.**

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
