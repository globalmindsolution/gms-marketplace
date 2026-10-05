# Finish — the result document's `states`, and the report

Read this when you write `result.json` in Finish and when you report: the
exact `states` keys the next steps read, what a failed run keeps, and what
the final message says.

Canonical `states` keys — EXACT names; `acs step finish` documents
them and the next steps read them:
- `plan_path`: where `plan.md` was published (the Development folder, or
  the partition when there is no checkout or feature to anchor it to).
  `/acs:code`'s gate resolves the file itself; this records which path
  this run chose.
- `plan_approved`: always `false` here. Approval is judged per delivery
  path, and the path does not exist yet when this skill runs — the
  `code-standard` and `code-complex` legs establish it at their own Start
  (ADR-0095). Recording `false` is the honest value, not a failure.
- `file_map`: the declared executor file map as `acs.py filemap set`
  returned it (task id → repo paths), so a later run can see what scope the
  plan claimed.
- `files`: every repo-relative path this run wrote and left uncommitted
  (the published `plan.md`; empty when the plan went to the partition or
  was kept local).
  `/acs:create-pr` commits them.

On failure keep whatever is true: the `plan_path` only when a plan was
actually published, `plan_approved: false`, the file map as far as it was
declared, open findings in `findings`, and the reason (iteration cap,
needs input, user chose to split) in `summary`.

## The report

3. Report a compact summary to the user: the published plan path (an
   uncommitted file in the working tree), the executor
   tasks and whether their file maps are disjoint, the AC-to-test mapping
   count, approval, open findings, and the next step (`/acs:code <id>`, or
   `/acs:create-ticket split <id> per <plan path>` after a split answer). Under /acs:ship, instead return ONLY the `<handoff>` XML as
   your final message — status, summary (≤1 KB), `<artifacts>` listing the plan
   path, and `<next-step>` pointing at `/acs:code <ticket-id>` (or at
   `/acs:create-ticket split <ticket-id>` after a split answer).
