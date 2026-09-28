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
    `/run-e2e-tests`, `/create-pr`, `/merge-pr` — each a skill directory
    with no per-skill manifest (ADR-0109), bundled alongside the default
    `workflows/ship.yaml` the delivery order is declared in (ADR-0089 as
    superseded by ADR-0096).
  - **Subagents**, one agent file per role a skill's own logic needs, named
    `<skill>-<role>` for the work it does (ADR-0109): the twelve
    **authoring skills** and `create-docs` each bundle a write role and a
    judge role —
    `analyze-requirements` (analyst, impact-reviewer), `create-prd` and
    `create-requirements` (plus a surveyor: surveyor, author, reviewer),
    `create-architecture` (architect, reviewer), `create-design` (designer,
    design-reviewer), `create-docs` (author, reviewer — one pair serving all
    four doc sets, ADR-0094), `create-impl-plan` (planner, plan-reviewer),
    `create-api-contract` (contract-author, contract-reviewer),
    `create-test-docs` (test-designer, trace-reviewer), `create-e2e-tests`
    (test-writer, suite-runner), `docs-sync` (doc-updater, drift-reviewer),
    `create-project` (scaffolder, build-checker) and `standardize-project`
    (plus an auditor: auditor, scaffolder, additive-checker); `code` bundles
    one implementer, its plan phase having moved to `create-impl-plan`
    (ADR-0089) and its review to `review-code`, which bundles a lens and an
    adjudicator; the three **apply-work skills** (`create-ticket`,
    `create-pr`, `merge-pr`) run inline and bundle no subagent.
    32 agent files exist on disk and 32 are reachable (27 for the twelve
    authoring skills + 2 for `create-docs` + 1 for `code` + 2 for
    `review-code`): every file name
    resolves to a shipped skill and a role in `acs_lib.skills.ROLE_KINDS`,
    so none is orphaned. See
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
