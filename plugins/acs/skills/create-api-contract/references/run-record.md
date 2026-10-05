# The run record — where `api-contract.md` goes, and whether it is shared

Read this at Start step 3: it resolves `<contract_path>`, the per-run record
this change publishes, and asks acs whether run documents are shared.

## Resolution

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" artifacts show
```

It resolves by the run the checkout points at (`--run <run-id>` names
another): design records in `<architecture_dir>/lld/<feature>/<id>/`, the
run's analysis and Development documents in `<development_dir>/<feature>/<id>/`,
the feature's living analysis in `<prd_dir>/features/<feature>/analysis/`
(`feature_analysis`, its `README.md`), and a legacy `docs/tickets/<ID>/` file
only when the new folder has none.

- `artifacts["api-contract.md"]` non-null → that existing file is the run
  record; this run REVISES it (a second pass on the same change, a review
  finding) — a legacy `docs/tickets/<ID>/api-contract.md` is revised by
  publishing to `paths["api-contract.md"]`. One record per change, one name.
- else `paths["api-contract.md"]` non-null → publish there.
- else → publish to `<partition>/api-contract.md`.

Call it `<contract_path>`; record it as `states.contract_path`. The same call
reports `artifacts["analysis.md"]` (the analysis folder's `README.md`;
`analysis_files` lists its context files) and `artifacts["design.md"]` — the
inputs every subagent is handed.

## Share or keep local — asked once, in the same grouped ask (ADR-0132)

Local-only sharing applies to the run record ONLY: the interface documents
under `lld/<feature>/api/` are living documents and always shared. Whether the
run record enters the repo is a saved choice, not yours. Before anything is
written, ask acs:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" docs where --doc api-contract.md
```

- **`needs` empty** → follow it silently. `share: true` publishes to `path`,
  the Design folder; `share: false` keeps the record LOCAL — `path` is in the
  run's state folder (`steps/create-api-contract/local/api-contract.md`),
  later steps still read it through `acs.py artifacts show`, it never enters
  `states.files`, and `/acs:create-pr` never commits it. Either way
  `<contract_path>` is its `abs_path`.
- **`needs` non-empty** → its questions join this skill's ONE grouped ask,
  never a separate one. `share`: "share run documents in the repo, or keep
  them local?" and "save this for you (this machine:
  `.acs/settings.local.json`) or for the team (`.acs/settings.json`)?".
  `location` (`location_source: default`): "use `proposed_path`, give another
  repo-relative folder, or keep documents local?" — keeping them local is the
  share answer, so ask its scope too. Record the answers in the ledger, then
  save them in ONE call carrying only what was answered — it prints the new
  `where`: `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" docs decide --share yes --scope team --location architecture=docs/architecture --doc api-contract.md`.
- **The user cannot be reached** (headless) and `needs` is non-empty → keep
  the record LOCAL for this run only — `acs.py docs decide --share no --scope
  run`, nothing saved — and say so in the report.

The completion report names where it went: "shared to <path>", "kept local
(team default)", "kept local (your default)" or "kept local (this run only)".
