# HLD — Tech stack & conventions

| Layer | Technology | Why |
|-------|------------|-----|
| acs Skills (30) | Markdown SKILL.md, Claude Code plugin skill format | acs coordinator protocols; user-invocable as `/acs:<name>` |
| Subagents (32 files, all reachable) | Markdown agent definitions | Separate executor and verifier contexts for the twelve authoring skills (24 agents) — no planner since ADR 0092 — plus `create-docs` (2; ADR 0094); four executor-only skills, the three apply-work ones and `code`, whose review left for `/acs:review-code` (4); and `review-code`'s own lens + adjudicator, which are not a pair — five lenses raise findings in parallel and one fresh-context adjudicator per finding tries to refute each (2); no agent file is orphaned; tool allowlists in frontmatter |
| Hooks & helpers | **Python ≥ 3.9, stdlib only** | Deterministic gating/persistence with zero consumer-machine installs |
| State | JSON (pretty-printed, atomic writes), JSON Schema 2020-12 | Human-auditable, machine-validated |
| Messaging | JSON validated against `schemas/result.schema.json` and `schemas/verdict.schema.json`, in the hook | Fail-fast malformed coordinator↔subagent traffic, with one schema language rather than two |
| Diagrams | Mermaid (C4, ER, sequence, state) | Diffable, GitHub-rendered, agent-maintainable |
| VCS / delivery | git, GitHub via `gh` CLI — acs's **sole** GitHub transport, by decision (ADR-0088; no MCP fallback) | Branch-per-ticket, PR-based delivery |
| Trackers (optional) | `gh` (Projects v2), `acli` (Jira) | Two-way sync; CLIs own auth — no secrets in settings; a failed `gh` call is classified **critical** (verbatim stderr + one canonical hint, stop) or **non-critical** (info finding + replayable command, continue) per ADR-0088 |
| CI / release | GitHub Actions | Per-plugin shape-conditional tests + validation per PR (`tests/acs/`; per-plugin schemas, hooks, skills presence-gated; no eval calls in CI); tag-on-version-bump releases |
| Tests | `unittest` (stdlib) | Multi-plugin test discovery: `python3 -m unittest discover -s tests` finds every `tests/<plugin>/` package automatically; per-plugin `__init__.py` package markers prevent import collisions |

## Conventions

- **Naming**: skills `kebab-case` = directory name; agents `<skill>-<role>`;
  hooks `pre-/post-<skill>.py`; run ledger `runs/<run-id>/run.json`; step
  state `steps/<step>/state.json`; phase artifacts
  `steps/<step>/iter-<n>/<phase>.*`; ticket ids `<PREFIX>-<n>`.
- **Writes**: temp-file + `os.replace` (atomic); counters guarded by an
  `O_EXCL` spin lock; corrupt JSON read as "absent", reported, never fatal.
- **Failure policy**: gates fail **closed**; helper CLIs exit 2 with
  actionable stderr; bookkeeping a gate does not depend on (the gate
  evidence record, the guard-denial audit) fails **open** — it must never
  block work.
- **Python compatibility**: 3.9+ (no `match`, no `X | Y` unions); `python3`
  on PATH is the only assumption.
- **Docs altitude**: requirements (`docs/0*.md`) → PRD (`docs/product/`) →
  this doc set (`docs/architecture/`) → implementation contract
  (`plugins/acs/docs/INTERNALS.md`) → authoring standard (`AUTHORING.md`).
