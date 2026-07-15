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
  - **Skills** (slash commands): `/init`, `/ship`, `/handoff`, `/update`,
    `/create-prd`, `/create-architecture`, `/create-project`,
    `/create-ticket`, `/create-design`, `/create-spec`, `/code`,
    `/create-pr`, `/merge-pr`.
  - **Subagents**: the twelve **triad-keeping skills** (`create-spec`, `code`,
    `create-prd`, `create-design`, `create-architecture`, `create-project`,
    `create-quality`, `create-operations`, `create-principles`,
    `create-standards`, `standardize-project`, `create-requirements`)
    each bundle a planner, executor, and verifier (e.g. `code-planner`,
    `code-executor`, `code-verifier`); the three **apply-work skills**
    (`create-ticket`, `create-pr`, `merge-pr`) run inline and ship only an
    executor (MAR-60 inlining). 45 agent files exist on disk (15 × 3 roles);
    39 are reachable (36 triad + 3 apply-work executors), and 6 — the
    apply-work planner/verifier files — are orphaned. See
    [../functional/reflection.md](../functional/reflection.md).
  - **Hooks**: a pre and post hook per workflow skill and per product-level
    skill, implemented as Python scripts
    (e.g. `pre-code.py`, `post-code.py`).
  - MAY bundle optional extras wired by `/init` on user consent — e.g. the
    status-line scripts (prompt line and agent-panel line).

## Distribution & versioning

- acs is distributed via **GitHub URL only**: users add the marketplace with
  `claude plugin marketplace add <github-url>` and install `acs` from it. No
  other registry/channel for now.
- acs follows **semver**, maintains a **CHANGELOG.md**, and releases are
  **automated** (CI release workflow tags versions and updates the
  changelog).
