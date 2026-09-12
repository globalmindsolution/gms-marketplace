# Packaging & distribution

Quality requirements for how `acs` is bundled and shipped. Moved out of
`overview.md`'s "Packaging requirements" and "Distribution & versioning"
sections during the MAR-145 functional/non-functional reorg (content
unchanged).

## Packaging requirements

- acs MUST be distributed through a marketplace manifest
  (`.claude-plugin/marketplace.json`) so users can add it with
  `claude plugin marketplace add` (or the equivalent UI flow) and install it.
- acs MUST bundle, per standard Claude Code plugin layout:
  - **Skills** (slash commands): `/setup`, `/ship`, `/handoff`, `/update`,
    `/create-prd`, `/create-architecture`, `/create-project`,
    `/create-ticket`, `/create-design`, `/analyze-ticket`,
    `/create-impl-plan`, `/create-api-contract`, `/create-test-docs`,
    `/code`, `/create-e2e-tests`, `/docs-sync`, `/run-e2e-tests`,
    `/create-pr`, `/merge-pr` — grouped into phases by
    `workflows/phases.yaml`, which acs MUST also bundle alongside the default
    `workflows/ship.yaml` the delivery order is declared in (ADR-0089).
  - **Subagents**: the sixteen **triad-keeping skills** (`create-prd`,
    `create-design`, `create-architecture`, `create-project`,
    `create-quality`, `create-operations`, `create-principles`,
    `create-standards`, `create-requirements`, `standardize-project`,
    `analyze-ticket`, `create-impl-plan`, `create-api-contract`,
    `create-test-docs`, `create-e2e-tests`, `docs-sync`) each bundle a
    planner, executor, and verifier (e.g. `docs-sync-planner`,
    `docs-sync-executor`, `docs-sync-verifier`); `code` bundles an executor
    and a verifier only, its plan phase having moved to `create-impl-plan`
    (ADR-0089); the three **apply-work skills** (`create-ticket`,
    `create-pr`, `merge-pr`) run inline and ship only an executor (MAR-60
    inlining). 59 agent files exist on disk; 53 are reachable (48 triad + 2
    for `code` + 3 apply-work executors), and 6 — the apply-work
    planner/verifier files — are orphaned. See
    [../functional/reflection.md](../functional/reflection.md).
  - **Hooks**: a pre and post hook per hooked skill (twenty of each),
    implemented as Python scripts (e.g. `pre-code.py`, `post-code.py`).
  - MAY bundle optional extras wired by `/setup` on user consent — e.g. the
    status-line scripts (prompt line and agent-panel line).

## Distribution & versioning

- acs is distributed via **GitHub URL only**: users add the marketplace with
  `claude plugin marketplace add <github-url>` and install `acs` from it. No
  other registry/channel for now.
- acs follows **semver**, maintains a **CHANGELOG.md**, and releases are
  **automated** (CI release workflow tags versions and updates the
  changelog).
