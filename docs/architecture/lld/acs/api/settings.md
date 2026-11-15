---
status: "implemented"
version: 1
tickets: []
feature: "acs"
---

# API — Settings

The consumer repo's settings files, the keys they carry, and the conformance chain those settings serve.

## Settings (consumer repo)

`.acs/settings.json` (+ gitignored `settings.local.json`, user-scope file);
per-key merge local → project → user over `DEFAULT_SETTINGS`; every file is
optional — with none, every key resolves to its default and no pre-hook
refuses ([ADR-0105](../../../adr/0105-acs-runs-without-setup.md)); validated by
every pre-hook, which still refuses a malformed value
(`settings.schema.json`): `ticket_prefix` (default `ACS`),
`merge_strategy`, `tests`, `workflow`, `models`, `tracker`, `release?`
(plus a tolerated `evals` object that nothing reads).
`tests` is `{coverage?, unit?, e2e?, <name>?}`: `coverage` is the TDD target and
CI-gate floor (default 90, exported to the gate as `ACS_COVERAGE`), `unit` is the
CI tests-gate suite (`{command, setup?}`), and every other key is a named suite
`{command, setup?, teardown?}` — the end-to-end suite is `tests.e2e`. The old
top-level `test_coverage_percent`, `suites` and `e2e` keys are gone: a file that
still carries them makes every acs skill refuse to start until
`acs.py settings migrate [--write]` rewrites it. `tracker.provider` is `local` or
`github`; `gh` is the only tracker transport.
`models` is `models.<skill>.<role> = {model?, effort?}`: an absent skill, role or
field, or the value `inherit`, inherits the parent session; the skills and roles
are the agents the plugin ships, and `acs.py settings scaffold --write` writes the
full block ([ADR-0115](../../../adr/0115-models-per-skill-and-role-through-generated-agents.md)).
There is no `formats` or `enforcement` block: branch, commit and PR-title style are
the model's to follow, and what a script must parse is fixed in
`acs_lib.conventions` — the branch name `<type>/<ticket_id>-<slug>`, the
CI exemptions (`acs-exempt`, `release/*`, `dependabot/*`, `renovate/*`), the `ACS`
pipeline label and the built-in template names (a repo's
`.acs/templates/<name>.md` of the same name replaces one). A `formats`,
`enforcement` or `hook_gates` block a repo still carries is accepted and ignored.
`tests.unit` backs the opt-in CI gates `/acs:setup` can scaffold (offered at Step 2,
installed by Step 3's `setup apply`): `acs-conventions.yml`+`check-conventions.py`,
which checks one rule, that the PR description names its ticket
([ADR-0106](../../../adr/0106-ci-checks-the-ticket-link-only.md)), and
`acs-tests.yml`+`run-tests.py` (`tests.unit`). The e2e
CI-gate artifact family (the same install, offered only when an e2e suite is
configured) is the same
shape: `acs-e2e.yml` + `run-e2e.py` (the committed
template pair), built from `tests.e2e` — no dedicated settings key of
its own — and wired as the `E2E suite` required-check context.
`/acs:setup` is optional; it writes only the project file, and only the gates'
keys (`tests.unit.command`); `setup_wizard.split_defaults` drops any
answer equal to its built-in default and removes one an earlier run wrote.
Every other key, `ticket_prefix` included, is edited by hand.
`templates/ci/check-conventions.py` runs without the plugin, so it holds its own
copy of the few constants it checks against (a test fails when the copies differ)
and checks a repo with no settings file against them.
No key locates the workspace or a document ([ADR-0102](../../../adr/0102-documents-are-found-not-configured.md)): the
workspace is always `<main-checkout>/.acs/state-machine` (anchored via
`git rev-parse --git-common-dir`, ADR-0086; ignored by its own `.gitignore`
of `*`, which `write_json`/`write_text` create on the first write under it,
ADR-0105), a run's documents go one folder per phase — Discovery
`<prd_dir>/features/<feature>/`, Design `<architecture_dir>/lld/<feature>/<id>/`,
Development `docs/development/<feature>/<id>/`, the directories resolved by
`acs_lib.requirements.prd_dir`/`architecture_dir`/`development_dir`
([ADR-0128](../../../adr/0128-requirements-from-any-container.md)); a legacy
`docs/tickets/<ID>/` is only read — and a skill finds every other repo document
through `CLAUDE.md` and the repo, creating a missing one at its `docs/`
convention. Settings record two kinds of answer under `docs`
([ADR-0132](../../../adr/0132-share-or-keep-run-documents-local.md)):
`share_run_documents` (a run's own documents shared to the phase folders, or
kept local in the run's step folders) and a `docs.<kind>_dir` saved when the
user confirms a phase folder that resolved only to the built-in default — acs
creates no such folder without that answer. `release_notes.py --workspace` ([cli.md](cli.md)) is unaffected in shape —
still an absolute path argument — and its caller passes this resolved
value.
The design template is the built-in `design-default`, or a repo's
`.acs/templates/design-default.md`; the required-section list is derived from the
template itself, so the built-in default encodes today's exact required-section
list (ADR 0065). create-tech-design's reviewer enforces the resolved
list as a blocking `structure` dimension via `structure_lint.py`.
The requirements set (found in the repo, else `docs/requirements/`) has a
**functional** and a **non-functional** subfolder (`functional/` and
`non-functional/` by default; an existing set's own names are followed).
acs no longer has a producer skill that bootstraps the set
([ADR-0118](../../../adr/0118-discovery-design-development-phases.md) removed
`/acs:create-requirements`): a set a repo keeps is optional context its
readers use, and the documentation step's requirements merge writes into the
same model as tickets change behavior. Code-cited coverage stays 100% — relocated,
never reduced — but a code-cited clause's citation(s) live in that doc's
companion `.evidence.md` sidecar, not inline in the body; the body keeps the
clause text, its stable anchor, and any C-22 `DRAFT — human-confirm-required`
marker (the sidecar convention, Decision B / ADR 0064).

Conformance chain: `PRD → architecture → principles → standards → design → code`, each level verified against the one above it.

Requirements (`docs/requirements/` by default, `functional/`+`non-functional/` subfolders) is a **living behavioral contract** that travels ALONGSIDE this chain — kept by the repo when it keeps one, accreted by `/acs:code`'s documentation step, read by `/acs:create-ticket` as current behavior — but it is **not a verified conformance level**: no code review dimension checks a ticket's conformance against the requirements set the way each chain level is verified against the one above it (D1; ADR 0060/0061/0062). The chain line is unchanged; this note only clarifies where requirements sits relative to it.

`/create-prd`'s output contract now additionally includes the **"Release
versions"** mapping table in `roadmap.md` (one row per release version →
milestone/wave + epic(s) delivered), verified by the create-prd reviewer's
0-orphan-milestone coverage sub-check (ADR 0053).

The `standards` chain level has a documentary counterpart in this repo at
`docs/standards/standards.md` (e.g. the test-file-naming standard); these
standards are enforced by guard tests and pipeline guidance rather than as a
runtime-verified conformance level.

The principles and standards levels, and the quality and operations sets
beside the chain, are written by hand. No skill bootstraps them since
[ADR-0124](../../../adr/0124-remove-create-docs.md) removed `/acs:create-docs`,
and with it the `DOC_SETS` table, its fan-out helpers and its argument parser.
The skills that read a set find it where the repo keeps it (ADR-0102); a
standards reader treats an absent principles set as not applicable, never as
a block, so the chain's "each level verified against the one above it" holds
wherever both levels exist.
