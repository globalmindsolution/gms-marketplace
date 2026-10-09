# /acs:create-pr — resuming an interrupted run

Open this when `context.reconcile` is true or `context.handoff_summary` is set.
Check recorded state against reality BEFORE committing or creating anything: a
commit made twice and a second PR for one run are the mistakes this step cannot
quietly undo.

- Read `steps/create-pr/state.json` and any `iter-*/commit-plan.json`. A confirmed
  plan on disk is the user's answer: do not re-plan or ask again.
- Compare it with git: is the plan's branch checked out, and which group subjects
  are already commits on it? Resume from the first uncommitted group by writing
  the remaining groups, unchanged and in order, to `commit-plan.resume.json` and
  running `acs.py pr commit --plan` on it (it refuses a path that is no longer an
  uncommitted change, so nothing is committed twice). Record the earlier commits
  from `git log` as well as the new ones.
- If the branch carries commits the plan does not account for, or its paths
  changed since it was confirmed, show the user what you found and ask.
- Check origin for the branch and for an open PR on it. A PR recorded but missing
  remotely is not done; a PR that exists but was never recorded is
  done-but-unfinalized: verify it, then finish normally.
- With `handoff_summary`, read it and `steps/create-pr/handoff-context.md`, trust
  it, spot-check the branch, commits and PR it names, and continue from there.
