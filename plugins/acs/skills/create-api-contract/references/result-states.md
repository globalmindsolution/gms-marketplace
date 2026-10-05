# The result document — canonical `states` and the two outcomes

Read this when you write `result.json` in Finish: the exact `states` keys the
next steps read, the two `outcome` values, and what a failed run keeps.

Canonical `states` keys — EXACT names; `acs step finish`
documents them and the next steps read them:
- `contract_path`: where `api-contract.md` was published (the design
  record folder, or the partition when there is no checkout or feature to
  anchor it to).
- `items` (int): how many endpoints/commands/messages the contract
  declares — the same number as the front matter's `items` and as the
  `### ` subsections under `## Surface`.
- `traced_acs` (list): the acceptance-criteria ids the items trace to, each
  appearing at least once in `## Traceability` (the union of the slices'
  reports when the contract-authors ran sliced).
- `files` (list): every repo-relative path this run wrote and left
  uncommitted — the published contract (not when kept local) plus each
  machine-readable contract file the slices' reports list. `/acs:create-pr` commits them.

`outcome` is required on every `completed` result document — the post-hook
refuses one without it, because this step completes in two ways: `contract_written`
when the loop ran, `no_surface_owed` when the survey found no surface to
specify (then `items` is `0` and `traced_acs` is `[]`). The pre-hook
records `no_surface_owed` itself when the plan's `## Contract` block owes
no contract, and this coordinator never runs.

The machine-readable contract files stay uncommitted in the working tree,
listed in `files`; name them in the completion report too. On failure
keep whatever is true: `contract_path` only when a contract was actually
published, the open findings in `findings`, and the reason (iteration cap,
needs input) in `summary`.
