# HLD — Tech stack & conventions

| Layer | Technology | Why |
|-------|------------|-----|
| acs Skills (28) | Markdown SKILL.md, Claude Code plugin skill format | acs coordinator protocols; user-invocable as `/acs:<name>` |
| Subagents (33 files, all reachable) | Markdown agent definitions | One file per role a skill's own logic needs, named `<skill>-<role>` for its work, each role of kind survey, write or judge (ADR 0109): separate writer and judge contexts for the eleven authoring skills (27 agents, including the surveyor of `create-prd`, the impact analyst of `analyze-requirements` and the gap analysts of `create-architecture`, `create-data-design` and `create-flows`); `code`'s implementer (1); and `review-code`'s own lens + adjudicator, which are not a pair — five lenses raise findings in parallel and one fresh-context adjudicator per finding tries to refute each (2); the read-only `audit-design`'s gap analyst, a survey with no judge (1, ADR-0122); the read-only `audit-security`'s auditor and adjudicator — a survey per category and a refute-by-default judge per candidate finding, no writer (2, ADR-0123); the three apply-work skills run inline and own none; no agent file is orphaned; tool allowlists in frontmatter |
| Hooks & helpers | **Python ≥ 3.9, stdlib only** | Deterministic gating/persistence with zero consumer-machine installs |
| State | JSON (pretty-printed, atomic writes), JSON Schema 2020-12 | Human-auditable, machine-validated |
| Messaging | JSON validated against `schemas/result.schema.json` and `schemas/verdict.schema.json`, in the hook | Fail-fast malformed coordinator↔subagent traffic, with one schema language rather than two |
| Diagrams | Mermaid (C4, ER, sequence, state) | Diffable, GitHub-rendered, agent-maintainable |
| VCS / delivery | git, GitHub via `gh` CLI — acs's **sole** GitHub transport, by decision (ADR-0088; no MCP fallback) | Branch-per-ticket, PR-based delivery |
| Trackers (optional) | `gh` (Projects v2) | Two-way sync; the CLI owns auth — no secrets in settings; a failed `gh` call is classified **critical** (verbatim stderr + one canonical hint, stop) or **non-critical** (info finding + replayable command, continue) per ADR-0088 |
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
