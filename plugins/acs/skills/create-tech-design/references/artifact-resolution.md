# Where the tech design lives — artifact resolution and share-or-keep-local

Read at Start, before anything is written.

## Tech design artifact resolution

`tech-design.md` is the change's tech design — ONE file per ticket (or per
ticketless run), one name, on every run. It is a human-facing document, the
hand-off the team reviews before implementation: it lives in the Design
phase's folder in the consumer repo, `<architecture_dir>/lld/<feature>/<id>/`,
beside `api-contract.md` and next to the feature's living LLD (ADR-0128,
superseding ADR-0090's ticket docs tree) — unless run documents are kept local
(below). Resolve where it lives before anything else:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" artifacts show
```

It resolves by the run the checkout points at (`--run <run-id>` names
another): design records in `<architecture_dir>/lld/<feature>/<id>/`,
Development documents in `<development_dir>/<feature>/<id>/`, the feature's
living analysis in `<prd_dir>/features/<feature>/analysis/`
(`feature_analysis`, its `README.md`), and a legacy `docs/tickets/<ID>/` file only when the new
folder has none — read only, nothing writes there.

- `artifacts["tech-design.md"]` non-null → that existing file is the design;
  this run REVISES it (a re-design after new information, never a second
  file). When the file it names is called `design.md`, it is a **legacy design
  record** — the name before ADR-0135, which every reader still falls back to
  while no `tech-design.md` exists (in the design record folder, a legacy
  `docs/tickets/<ID>/`, the old local step folder or the partition): read it
  as the starting point and publish the revision to `paths["tech-design.md"]`;
  the legacy file is left as it is and named in the report.
- else `paths["tech-design.md"]` non-null → the design is published there.
- else (no checkout, or no feature recorded for the run yet) → the design is
  published to `<partition>/tech-design.md` and nothing enters the repo.

This is exactly what `acs_lib.artifacts.artifact_path` resolves (the run
artifact `design`, with `tech-design` accepted as an alias) and what the
`design_approved` predicate and `/acs:code` look for, so the path this run
chooses is the path that opens the next gate. Call it `<design_path>` — for a
legacy record, the `paths["tech-design.md"]` the revision is published to.

The working draft lives at `steps/create-tech-design/tech-design.md`; the
published file is a copy of those exact bytes (Publish). The draft is
workspace state — the designer writes it and the reviewer judges it, and the
file-map guard denies any subagent a write to the published design.

**Seeding a re-design.** When an existing document was found above and the
draft does not exist yet in this run, seed the draft from it before the draft
pass, so the designer revises in place and the version history carries on:

```bash
cp "<the existing tech-design.md or legacy design.md>" "<partition>/steps/create-tech-design/tech-design.md"
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design bump --ticket <id> "<partition>/steps/create-tech-design/tech-design.md"
```

`design bump` adds one to `version`, records the ticket and re-opens an
approved or implemented design as `proposed`. A legacy `design.md` with no
front matter is not bumped — the `design init` after the draft pass gives it
its first block. Bump once per run: a draft that already exists (a resumed run)
is never re-seeded or bumped again. The designer rewrites the body under the
new section shape; the block stays the coordinator's.

## Share or keep local — asked once, in the same grouped ask (ADR-0132)

Whether `tech-design.md` enters the repo is a saved choice, not yours. Right
after the artifact resolution, before anything is written, ask acs:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" docs where --doc tech-design.md
```

- **`needs` empty** → follow it silently. `share: true` publishes to `path`,
  the phase folder; `share: false` keeps the document LOCAL — `path` is in the
  run's state folder (`steps/create-tech-design/local/tech-design.md`), later
  steps still read it through `acs.py artifacts show`, it never enters
  `states.files`, and `/acs:create-pr` never commits it. Either way
  `<design_path>` is its `abs_path`. A design kept local is a hand-off nobody
  else can review: say so in the report.
- **`needs` non-empty** → its questions join this skill's ONE grouped ask
  (User interaction), never a separate one; with no other question, ask them
  alone in one AskUserQuestion before Publish. `share`: "share run documents
  in the repo, or keep them local?" and "save this for you (this machine:
  `.acs/settings.local.json`) or for the team (`.acs/settings.json`)?".
  `location` (`location_source: default` — no setting, no existing folder):
  "use `proposed_path`, give another repo-relative folder, or keep documents
  local?" — keeping them local is the share answer, so ask its scope too. acs
  never creates a new docs folder without that answer. Record the answers in
  the ledger, then save them in ONE call carrying only what was answered — it
  prints the new `where`: `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" docs decide --share yes --scope team --location architecture=docs/architecture --doc tech-design.md`.
- **The user cannot be reached** (headless, nothing relayed in a `/acs:ship`
  brief) and `needs` is non-empty → keep the document LOCAL for this run only
  — `acs.py docs decide --share no --scope run`, nothing saved — and say so in
  the report.

The completion report names where it went: "shared to <path>", "kept local
(team default)", "kept local (your default)" or "kept local (this run only)".
