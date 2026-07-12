# Engineering principles

## Principles

1. **Consumer-repo generality** — every acs skill operates on the invoking consumer repo through `.acs/settings.json`; no skill ever hardcodes this marketplace's own layout or artifacts (`.claude-plugin/marketplace.json`, `plugins/acs/.claude-plugin/plugin.json`, the acs `source.ref`, `plugins/acs/CHANGELOG.md`, the `release.yml` workflow, or the `main` branch name). Settings-driven configuration is the mechanism: a skill reads the relevant path or behavior from `.acs/settings.json` rather than assuming this repo's own layout.
2. **One gated pipeline, no consumer-specific fork** — the same gated pipeline (define -> spec -> code -> PR -> merge) delivers every consumer repo acs operates on; no skill or gate is special-cased for any one product, including external commercial products acs delivers.
3. **Human-merge safety gate before any irreversible or outward-facing publish** — acs never tags, publishes, or merges itself; a human always approves the step that becomes visible outside the repo or cannot be undone (a merge, a release tag, a publish).
4. **Stdlib-only, runtime-agnostic deterministic core** — hooks and helpers target Python 3.9+ and import only the standard library, so no acs install is required on a CI runner and the deterministic core can target a second agent runtime without rewriting it.

## Rationale

### Consumer-repo generality

- **Problem prevented:** a skill that reads or writes this marketplace's own manifests, changelog, workflow file, or branch name breaks the moment it runs against any other consumer repo — the exact fork PRD constraint C-16 forbids, generalized by **C-20** to every skill (not only the external-product delivery path). C-20 also traces **G30** (external-consumer delivery readiness) and **G33** (full-SDLC phase coverage) — both require the same gated pipeline to behave identically across every repo it delivers.
- **Tradeoff accepted:** every skill must read its target path from `.acs/settings.json` instead of a convenient literal, which costs a small amount of indirection during authoring.
- **Violation cue:** a reviewer sees a skill, hook, or helper reference a literal path or name from this list — `.claude-plugin/marketplace.json`, `plugins/acs/.claude-plugin/plugin.json`, a hardcoded `source.ref`, `plugins/acs/CHANGELOG.md`, `release.yml`, or the `main` branch — outside of this repo's own dogfooding tooling (`.acs/`, `tests/acs/`, `evals/`).
- **Live violation on record:** `/acs:release` (MAR-129, held **PR #251**) was implemented marketplace-hardcoded — it reads and writes this repo's own `marketplace.json`/`plugin.json`/`CHANGELOG.md`/`release.yml` directly. It is being re-scoped settings-driven (a new `.acs/settings.json` `release` block, with this marketplace as configured profile #1) under the **MAR-128** epic. **Enforcement note:** principle-conformance checking of this rule by the design and code verifiers activates once the installed plugin is updated from 0.3.7 to v0.4.x — the 0.3.7 install does not yet enforce it.

### One gated pipeline, no consumer-specific fork

- **Problem prevented:** a parallel or special-cased workflow for one product (e.g. the external hiring-SaaS consumer under **G30**) silently drifts from the audited pipeline and reintroduces the two-pipeline risk **C-16** exists to close.
- **Tradeoff accepted:** a product with unusual needs must be served by extending the shared pipeline's configuration surface, not by branching the pipeline itself — sometimes slower than a bespoke shortcut.
- **Violation cue:** a reviewer finds a skill, gate, or code path keyed on a specific repo's or product's identity (an `if repo == ...` branch, a product-named skill).

### Human-merge safety gate before any irreversible or outward-facing publish

- **Problem prevented:** an agent-only merge/tag/publish path removes the last human checkpoint before an action that cannot be undone or that becomes externally visible — the failure mode **G26** (invoker-scoped merge governance) and the "acs never tags/publishes itself" invariant (**C-20**) both guard against.
- **Tradeoff accepted:** every release or merge waits on a human action even when the pipeline is otherwise fully autonomous.
- **Violation cue:** a reviewer finds a code path that calls `git push --tags`, `gh release create`, or merges a PR without a preceding human-invoked gate.

### Stdlib-only, runtime-agnostic deterministic core

- **Problem prevented:** a third-party dependency in the deterministic layer (hooks, gating, id allocation, convention checks) would force a pip install on every CI runner and couple the core to one agent runtime, blocking the **Portability NFR** and goal **G6**.
- **Tradeoff accepted:** helpers forgo convenience libraries (e.g. richer CLI/YAML/HTTP packages) in favor of stdlib primitives, sometimes costing more code.
- **Violation cue:** a reviewer finds a hook or helper script under `plugins/acs/hooks/` or `.acs/ci/` with a non-stdlib top-level `import`, or syntax requiring Python newer than 3.9.
