# The result document — canonical `states` and the two outcomes

Read this when you write `result.json` in Finish: the exact `states` keys the
next steps read, the two `outcome` values, and what a failed run keeps.

Canonical `states` keys — EXACT names; `post-create-api-contract.py`
documents them and the next steps read them:

- `contract_path`: where the run record `api-contract.md` was published —
  repo-relative in the Design folder when shared, its partition path when kept
  local (ADR-0132).
- `feature` (list): the PRD feature slugs this run designed.
- `files` (list): EVERY repo-relative path this run wrote and left
  uncommitted — the interface documents, the README files, and the run record
  when it is shared (never one kept local). `/acs:create-pr` commits them in
  its `design` layer.
- `types` (list): the owned LLD types written — `["api-contract"]`, or `[]`.
- `interfaces` (list): the repo-relative paths of the interface documents
  under `lld/<feature>/api/` this run created or bumped — the same list as the
  run record's `interfaces` front matter.
- `items` (int): how many operations, commands, messages or signatures the
  run specified across those documents — the same number as the run record's
  `items` and as the `### ` subsections under their `## Surface`.
- `traced_acs` (list): the acceptance-criteria ids the items trace to, each
  appearing at least once in a `## Traceability` table (the union of the
  writer slices' reports when they ran sliced).
- `gaps` (object): `{"undocumented": n, "unimplemented": n, "drifted": n}` from
  `iter-1/gaps.md`, zeros when there was nothing to compare.

`outcome` is required on every `completed` result document — the post-hook
refuses one without it, because this step completes in two ways:
`contract_written` when the loop ran and the review passed, `type_disabled`
when `design.lld_types` does not enable `api-contract` (then every list is
`[]`, `items` is `0`, the gap counts are zeros, and nothing was written).

Nothing here is a machine-readable contract file: this skill writes documents
only. On failure keep whatever is true: the interface documents written so far
in `files` and `interfaces`, `contract_path` only when the record was actually
published, the open findings in `findings`, and the reason (iteration cap,
needs input) in `summary`.
