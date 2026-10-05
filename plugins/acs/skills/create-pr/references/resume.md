# /acs:create-pr — resuming an interrupted run

Open this when `context.reconcile` is true, or when `context.handoff_summary`
is set. A run that commits and opens the PR in one session reads none of it.
Two things may already exist from the prior run: commits of a confirmed plan,
and a PR for the branch. The reality check comes before anything is committed
or created, because a commit made twice and a second PR for one run are the
mistakes this step cannot quietly undo.

**Where the cross-references below point.** The numbered steps are the Inline
apply flow's, in SKILL.md (C1–C4 the commit phase, 1–7 the publish phase).

## Resume & reconcile

If `context.reconcile` is true, verify recorded state against reality BEFORE
continuing:

1. Read `steps/create-pr/state.json` (`invocations[-1]`) and any
   `steps/create-pr/iter-*/publish.json` and `iter-*/commit-plan.json` to see
   how far the prior run got.
2. **A confirmed plan on disk** (`iter-<n>/commit-plan.json`) is the user's
   answer: do not re-plan and do not ask again. Check the commit phase against
   git, not against the publish report: is the plan's branch checked out
   (`git rev-parse --abbrev-ref HEAD`), and which of its group subjects are
   already commits on it (`git log --format='%H %s' <plan.base>..<branch>`)?
   - Some groups committed, some not (the run stopped mid-plan): resume from
     the first uncommitted group. A group is committed when its subject is a
     commit on the branch and none of its paths is still an uncommitted
     change (`acs.py changes diff --since HEAD --name-only`). Write the
     groups from the first uncommitted one on, unchanged and in order, to
     `steps/create-pr/iter-<n>/commit-plan.resume.json` (same branch) and run
     `acs.py pr commit --plan` on that file: it is already on the branch, so
     it only commits. `pr commit` refuses a path that is no longer an
     uncommitted change, which is what keeps a group from being committed
     twice. Record the earlier commits from `git log` and the new ones as
     printed.
   - Every group committed: go on to the publish phase (step 1).
   - The branch carries commits the plan does not account for, or the plan's
     paths changed again since it was confirmed: that is reality diverging
     from state — show the user what you found and ask (SKILL.md's User
     interaction) before committing anything more.
   - No confirmed plan, or the prior run was cancelled at the preview: start
     at C1 as a fresh run does.
3. Re-check the publish phase: does the branch exist on origin
   (`git ls-remote origin <branch>`)? Does an open PR for it exist
   (`gh pr list --head <branch> --state open --json number,url,baseRefName`)?
   A PR recorded but missing remotely is not done; a PR that exists but was
   never recorded is done-but-unfinalized — verify it, then finish normally.
4. Continue from the first unfinished phase of the recorded iteration, and
   record in `states.commits` every commit of the plan — the ones the prior run
   made as well as yours.

If `context.handoff_summary` exists, read it plus
`steps/create-pr/handoff-context.md` (if present), do a light
reconcile (trust the summary, cheaply spot-check the branch, its commits and
the PR it names), and continue from where it points.
