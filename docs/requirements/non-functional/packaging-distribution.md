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
    `/release`, `/create-prd`, `/create-architecture`,
    `/create-ticket`, `/create-design`, `/analyze-requirements`,
    `/create-impl-plan`, `/create-api-contract`, `/create-test-docs`,
    `/code`, `/review-code`, `/create-e2e-tests`, `/docs-sync`,
    `/run-e2e-tests`, `/create-pr`, `/merge-pr`, `/audit-design`,
    `/audit-security` — each a skill directory
    with no per-skill manifest (ADR-0109), bundled alongside the default
    `workflows/ship.yaml` the delivery order is declared in (ADR-0089 as
    superseded by ADR-0096).
  - **Subagents**, one agent file per role a skill's own logic needs, named
    `<skill>-<role>` for the work it does (ADR-0109): the nine
    **authoring skills** each bundle a write role and a judge role —
    `analyze-requirements` (plus an impact analyst: impact-analyst, analyst,
    impact-reviewer), `create-prd` (plus a surveyor: surveyor, author,
    reviewer),
    `create-architecture` (architect, gap-analyst, reviewer), `create-design` (designer,
    design-reviewer), `create-impl-plan` (planner, plan-reviewer),
    `create-api-contract` (contract-author, contract-reviewer),
    `create-test-docs` (test-designer, trace-reviewer), `create-e2e-tests`
    (test-writer, suite-runner) and `docs-sync` (doc-updater,
    drift-reviewer); `code` bundles
    one implementer, its plan phase having moved to `create-impl-plan`
    (ADR-0089) and its review to `review-code`, which bundles a lens and an
    adjudicator; the read-only `audit-design` bundles one gap analyst
    (ADR-0122) and the read-only `audit-security` an auditor and an
    adjudicator (ADR-0123); the three **apply-work skills** (`create-ticket`,
    `create-pr`, `merge-pr`) run inline and bundle no subagent.
    27 agent files exist on disk and 27 are reachable (21 for the nine
    authoring skills + 1 for `code` + 2 for
    `review-code` + 1 for `audit-design` + 2 for `audit-security`): every file name
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
