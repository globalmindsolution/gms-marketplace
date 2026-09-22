# /acs:create-pr — resuming an interrupted run

Open this when `context.reconcile` is true, or when `context.handoff_summary`
is set. A run that opens the PR in one session reads none of it. The whole
point of the procedure is that a PR may already exist for this branch: the
reality check comes before anything is created, because a second PR for one
ticket is the one mistake this step cannot undo.

**Where the cross-references below point.** The numbered steps are the Inline
apply flow's, in SKILL.md.

## Resume & reconcile

If `context.reconcile` is true, verify recorded state against reality BEFORE
continuing:

1. Read `<partition>/create-pr-state.json` (`runs[-1]`) and any
   `steps/create-pr/iter-*-*.xml` to see how far the prior run got.
2. Re-check reality: does the branch exist on origin
   (`git ls-remote origin <branch>`)? Does an open PR for it exist
   (`gh pr list --head <branch> --state open --json number,url,baseRefName`)?
   A PR recorded but missing remotely is not done; a PR that exists but was
   never recorded is done-but-unfinalized — verify it, then finish normally.
3. Continue from the first unfinished phase of the recorded iteration.

If `context.handoff_summary` exists, read it plus
`steps/create-pr/handoff-context.md` (if present), do a light
reconcile (trust the summary, cheaply spot-check the PR/branch it names), and
continue from where it points.
