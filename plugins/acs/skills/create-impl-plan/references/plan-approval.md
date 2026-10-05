# Plan approval — why it happens later, and who writes it

Read this when anyone asks this skill to approve the plan, or to run
`plan-approval.py`: approval is not this skill's step.

Approval binds on the `standard` and `complex` delivery paths only — and this
skill runs before any path exists, because `plan.md` is the artifact the path
is judged FROM. So `plan-approval.py` is not run here.

A human approves the plan with `plan-approval.py`, which is the **sole writer**
of `plan-approval.json` — never a coordinator, never a subagent, and never a
Write-tool call, because a record a skill can write itself is not an approval.
It hashes `steps/create-impl-plan/plan.md` into `plan_sha256`, and `/acs:code`'s
pre-hook refuses the deep paths when that digest does not match the plan on
disk. An edited plan is an unapproved plan.

What this skill owes approval is therefore one thing: **publish the plan and
leave it alone.**
