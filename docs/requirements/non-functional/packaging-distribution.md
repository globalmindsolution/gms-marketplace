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
    `/create-ticket`, `/create-design`, `/analyze-requirements`,
    `/create-impl-plan`, `/create-api-contract`, `/create-test-docs`,
    `/code`, `/review-code`, `/create-e2e-tests`, `/docs-sync`,
    `/run-e2e-tests`, `/create-pr`, `/merge-pr` — each declaring its own
    phase, reads and writes in `skills/<name>/acs.yaml`, which acs MUST also
    bundle alongside the default `workflows/ship.yaml` the delivery order is
    declared in (ADR-0089 as superseded by ADR-0096).
  - **Subagents**: the twelve **authoring skills** (`create-prd`,
    `create-design`, `create-architecture`, `create-project`,
    `create-requirements`, `standardize-project`,
    `analyze-requirements`, `create-impl-plan`, `create-api-contract`,
    `create-test-docs`, `create-e2e-tests`, `docs-sync`) each bundle an
    executor and a verifier (e.g. `docs-sync-executor`,
    `docs-sync-verifier`) and no planner (ADR-0092 class D: the executor
    surveys first and records `iter-<n>-authoring.md`); `code` bundles an
    executor and a verifier, its plan phase having moved to
    `create-impl-plan` (ADR-0089); `create-docs` bundles an executor and a
    verifier that serve all four doc sets (ADR-0094); the three **apply-work
    skills** (`create-ticket`, `create-pr`, `merge-pr`) run inline and ship
    only an executor (MAR-60 inlining).
    32 agent files exist on disk and 32 are reachable (24 for the twelve
    authoring skills + 2 for `code` + 2 for `create-docs` + 3 apply-work
    executors): ADR-0092 deleted the six apply-work planner/verifier files
    the skills already forbade spawning and, in its stage 2, the twelve
    authoring planners; ADR-0094 replaced the four doc legs' twelve files
    with two, and the registry now declares what each skill owns. See
    [../functional/reflection.md](../functional/reflection.md).
  - **Hooks**: a pre and post hook per hooked skill (seventeen of each),
    implemented as Python scripts (e.g. `pre-code.py`, `post-code.py`).

## Distribution & versioning

- acs is distributed via **GitHub URL only**: users add the marketplace with
  `claude plugin marketplace add <github-url>` and install `acs` from it. No
  other registry/channel for now.
- acs follows **semver**, maintains a **CHANGELOG.md**, and releases are
  **automated** (CI release workflow tags versions and updates the
  changelog).
