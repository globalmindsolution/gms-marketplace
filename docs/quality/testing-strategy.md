# Ensuring acs skill quality — a layered testing strategy

acs skills are **agentic**: they drive non-deterministic `claude` sessions, so a
skill's *output* cannot be unit-tested the way the deterministic layer can.
Quality therefore comes from a **pyramid of layers** — cheapest and most
deterministic at the base, most expensive and least deterministic at the top.

> **The rule:** push every check as far *down* the pyramid as it will go.
> Anything assertable deterministically (structure, schema-conformance, gate
> transitions) belongs in the free layers that gate every PR. Reserve paid,
> live-agent evals for what genuinely needs a running model.

## The pyramid

| # | Layer | What it verifies | Cost / determinism | Where | Runs |
|---|-------|------------------|--------------------|-------|------|
| 1 | Structural / contract | every skill & agent is wired right — frontmatter, lifecycle-script calls, completion reports, tool restrictions, grounding, phase artifacts | free, deterministic | [test_skill_contracts.py](../../tests/acs/test_skill_contracts.py) | every PR |
| 2 | Deterministic layer | gates block/advance, state/locks/counters/metrics, helper CLIs | free, deterministic | Every module that imports the shared `acs_case` fixture (`tests/acs/acs_case.py`) — **13** modules; re-derive with `grep -lE "^(import|from) acs_case" tests/acs/*.py` (a bare `grep -l acs_case` over-counts: `test_testing_conventions_guard.py` and `test_coverage_measurement_config.py` mention the fixture in prose without importing it): [`test_acs_case_fixture.py`](../../tests/acs/test_acs_case_fixture.py), [`test_acs_lib_gates.py`](../../tests/acs/test_acs_lib_gates.py), [`test_acs_lib_hook_entrypoints.py`](../../tests/acs/test_acs_lib_hook_entrypoints.py), [`test_acs_lib_settings.py`](../../tests/acs/test_acs_lib_settings.py), [`test_acs_lib_state_locks.py`](../../tests/acs/test_acs_lib_state_locks.py), [`test_acs_plugin.py`](../../tests/acs/test_acs_plugin.py), [`test_clarify.py`](../../tests/acs/test_clarify.py), [`test_codeowners.py`](../../tests/acs/test_codeowners.py), [`test_handoff.py`](../../tests/acs/test_handoff.py), [`test_new_ticket.py`](../../tests/acs/test_new_ticket.py), [`test_skill_start.py`](../../tests/acs/test_skill_start.py), [`test_statusline.py`](../../tests/acs/test_statusline.py), [`test_subagent_statusline.py`](../../tests/acs/test_subagent_statusline.py) (`test_testing_conventions_guard.py` deliberately does not import it — see its own docstring) | every PR |
| 3 | Static validation | JSON / JSON-Schema / XSD parse, byte-compile, version consistency | free, deterministic | [ci.yml](../../.github/workflows/ci.yml) | every PR |
| 4 | Free eval smoke | the *shipped build* still installs & gates; SessionEnd cleanup | free, deterministic | `evals/` (`install_gate_smoke`, `session_end_safety_net`) | pre-commit + CI |
| 5 | Trigger evals | the *right skill fires* for a natural-language request | paid (cheap), ~deterministic w/ re-probe | `evals/skill_triggers` | on-demand |
| 6 | Artifact / behavioral evals | a *real run* produces correct workspace artifacts | paid (costly), non-deterministic | `evals/` (`create_ticket_artifacts`, `resume_and_verify`) | pre-release |
| 7 | Runtime reflection verifier | each individual run's output is correct (in-band, per-run) | part of normal use | the plan→execute→verify cycle inside every skill | every real invocation |
| 8 | Dogfooding (E3) | end-to-end quality under real use | the cost of using acs | shipping acs changes via `/acs:ship` | ongoing |
| 9 | LLM-as-judge *(not built)* | subjective quality — is the PRD/design *sound*? | paid + noisy | future | pre-release for product skills |

Layers 1–4 are free and gate every PR (and, for layer 4, every commit via the
`acs-free-evals` pre-commit hook). Layers 5–6 are the paid
[eval harness](../../evals/README.md). Layer 7 is a *runtime control*, not a test.

## Coverage today (per skill)

24 shipped skills exist under `plugins/acs/skills/` — one directory per skill.
The on-disk `skills/*/SKILL.md` set is test-pinned by
`test_skill_contracts.py`'s `test_all_skills_exist_no_strays` (`:44-47`,
sorted `SKILL.md` glob vs sorted `ALL_SKILLS`) to equal `ALL_SKILLS` — a
hand-maintained literal declared in that same test module (`:20-25`), *not*
the runtime registry: that module imports only `glob`, `json`, `os`, `re` and
`unittest` (`:11-15`) and never `acs_lib`, so the pinned list and the
registry's `HOOKED_SKILLS`/`UNHOOKED_SKILLS` are two separately maintained
copies of the same skill names. That pin is why the count below is
re-derivable; it is not what keeps the table current. Two tests open this
markdown file during a full suite run, and neither asserts anything about the
table: `test_e2e_integrity_metric_docs.py:219-225` pins only the G13
e2e-integrity validation section below (its `G13`, `MAR-127`, "sub-metric (a)"
and "sub-metric (b)" markers), and `test_mermaid_diagrams.py:223-226` walks
the repo's Markdown (`_markdown_files`, `:34-42`) to lint Mermaid blocks. So
nothing yet stops a new skill shipping without a row here (see Roadmap
item 2). The registry at
[`acs_lib.py:41-44`](../../plugins/acs/hooks/scripts/acs_lib.py) splits them
into **15 hooked** (`PRODUCT_SKILLS` + `WORKFLOW_SKILLS`, each with a
`pre-*.py`/`post-*.py` pair and a planner/executor/verifier triad) and
**9 unhooked** (`UNHOOKED_SKILLS`). Figures anchored **as of `7a3368e`**;
re-derive with `ls -1 plugins/acs/skills | wc -l` (→ `24`) and a Python one-liner
importing `acs_lib` and printing `len(HOOKED_SKILLS)`, `len(UNHOOKED_SKILLS)`
(→ `15 9`).

Each column below is a **rule**, applied mechanically — a cell is derived,
never hand-picked:

- **Structure (1)** — the skill's `SKILL.md` is asserted by
  `test_skill_contracts.py` (`:46-47`) → 24 of 24.
- **Gate (2)** — the skill has a registered gate function in `acs_lib.GATES`
  → 15 of 15 hooked, pinned by `tests/acs/test_producer_skill_gates.py:42-47`
  (`test_all_hooked_skills_have_a_gate`, a per-hooked-skill
  `assertIn(skill, acs_lib.GATES)` loop); the 9 unhooked have none by
  construction, closed by `tests/acs/test_release_skill_registry.py:87`
  (`assertEqual(len(acs_lib.GATES), 15)` — with the loop above proving
  `GATES` ⊇ the 15 hooked skills, an equal count pins it to exactly that
  set) and `:71-72`, which separately confirms one such skill (`release`)
  is absent from `GATES`.
- **Trigger (5)** — the skill has a case in
  `evals/acs/scenarios/s04_skill_triggers.py`'s `CASES` → 22 of 24;
  `create-requirements` and `docs-sync` have none (`grep -rn
  "docs-sync\|create-requirements" evals/` returns no hits — neither skill
  appears anywhere under `evals/`).
- **Artifact (6)** — a layer-6 eval asserts that skill's own workspace
  artifacts → 3 of 24: `create-ticket`
  ([`s02_create_ticket_artifacts.py`](../../evals/acs/scenarios/s02_create_ticket_artifacts.py),
  forge-tier
  [`s07_fanout_tracker_sync.py`](../../evals/acs/scenarios/s07_fanout_tracker_sync.py)),
  `code`
  ([`s03_resume_and_verify.py`](../../evals/acs/scenarios/s03_resume_and_verify.py)),
  and `create-pr` (forge-tier
  [`s08_create_pr_forge.py`](../../evals/acs/scenarios/s08_create_pr_forge.py) —
  runs its real title/label/section assertions once a forge target is
  configured; skips cleanly otherwise, so this repo's own run of it is a skip,
  not live coverage).

**Hooked (15)**

| Skill | Structure (1) | Gate (2) | Trigger (5) | Artifact (6) |
|-------|:---:|:---:|:---:|:---:|
| `create-prd` | ✅ | ✅ | ✅ | — |
| `create-architecture` | ✅ | ✅ | ✅ | — |
| `create-project` | ✅ | ✅ | ✅ | — |
| `create-quality` | ✅ | ✅ | ✅ | — |
| `create-operations` | ✅ | ✅ | ✅ | — |
| `create-principles` | ✅ | ✅ | ✅ | — |
| `create-standards` | ✅ | ✅ | ✅ | — |
| `create-requirements` | ✅ | ✅ | — | — |
| `create-ticket` | ✅ | ✅ | ✅ | ✅ |
| `create-design` | ✅ | ✅ | ✅ | — |
| `code` | ✅ | ✅ | ✅ | ✅ |
| `docs-sync` | ✅ | ✅ | — | — |
| `create-pr` | ✅ | ✅ | ✅ | ✅ |
| `merge-pr` | ✅ | ✅ | ✅ | — |
| `standardize-project` | ✅ | ✅ | ✅ | — |

**Unhooked (9)**

| Skill | Structure (1) | Gate (2) | Trigger (5) | Artifact (6) |
|-------|:---:|:---:|:---:|:---:|
| `initialize` | ✅ | n/a (unhooked) | ✅ | — |
| `ship` | ✅ | n/a (unhooked) | ✅ | — |
| `handoff` | ✅ | n/a (unhooked) | ✅ | — |
| `update` | ✅ | n/a (unhooked) | ✅ | — |
| `install-hooks` | ✅ | n/a (unhooked) | ✅ | — |
| `metrics` | ✅ | n/a (unhooked) | ✅ | — |
| `usage` | ✅ | n/a (unhooked) | ✅ | — |
| `test` | ✅ | n/a (unhooked) | ✅ | — |
| `release` | ✅ | n/a (unhooked) | ✅ | — |

The remaining `merge-pr` Artifact `—` cell carries a specific reason rather
than being open gap: it needs a **forge tier** (a live GitHub remote). Its
harness foundation shipped in MAR-67 (`ForgeSandbox` +
`evals.forge_repo`/`ACS_FORGE_REPO` + non-production guards + branch-per-run
teardown, `evals/README.md:61`); `create-pr`'s forge-tier eval itself shipped
(`create_pr_forge`) — see "Roadmap to close the gap" item 3 for what still
blocks both cells from running their real assertions: an onboarded target
repo. The other 20 `—` cells are the gap itself.

**Structure is complete: 24 of 24** (`test_skill_contracts.py:44-47` pins the
on-disk set against the `ALL_SKILLS` literal at
`test_skill_contracts.py:20-25`, not against `acs_lib` — and no test pins this
table itself, so a new skill's row here is not enforced; see Roadmap item 2).
**Gating is complete for what can be gated: 15 of 15 hooked skills**; the other
9 are n/a by construction — no `pre-*.py`/`GATES` entry exists for them, and
none should. **Routing covers 22 of 24** — the two exceptions,
`create-requirements` and `docs-sync`, both shipped with no trigger eval. **The
gap is behavioral (artifact) coverage: only 3 of 24 skills** (`create-ticket`,
`code`, `create-pr`) are verified at the output level (`create-pr`'s eval
skips without a configured forge target) — so the *common* skill bugs (a
missing script reference, a malformed completion report, a broken gate, the
wrong skill firing) are already caught cheaply for nearly the whole surface.

## Principles

1. **Assert artifacts, never prose.** A scenario passes because the right JSON
   state exists with the right values — not because the model "said" the right
   thing. Validate produced artifacts against
   [`plugins/acs/schemas/*.schema.json`](../../plugins/acs/schemas/).
2. **Push checks down the pyramid.** Prefer a deterministic assertion (layers
   1–4) over a paid eval whenever the property is structural.
3. **One run, many assertions.** The live-agent run is the expensive part —
   once you've paid for it, validate *everything* about its output (schema
   conformance + completeness + gate progression), not just one field.
4. **The verifier is the runtime gate; tests are the regression net.** The
   reflection verifier catches a bad run in the moment; evals catch a regression
   in the skill across changes. They are complementary, not redundant.
5. **Cost-aware tiering.** Free tiers gate every commit/PR; the paid suite is a
   **pre-release gate** (`python3 evals/run_evals.py --paid` before tagging).
   Never put paid evals on a per-commit or scheduled path.
6. **Never assert equality or ordering on an `updated_at` value.**
   `acs_lib.now_iso()` is second-resolution (`acs_lib.py:391-392`); such an
   assertion survived an injected mutant in 17 of 20 runs in MAR-169.
   **Enforced** by `tests/acs/test_testing_conventions_guard.py` (detector 1,
   deliberately with no allowlist).
7. **Run all mutation testing on a copy outside the repo, synchronously —
   never in-tree, never backgrounded.** Two interrupted in-tree runs each
   left a MUTANT in `clarify.py`, and one left an orphaned background
   mutator that corrupted a coordinator diagnosis (MAR-177). **Not
   enforceable by a test** — a completed in-tree run restores the file and
   leaves no durable trace, so no test here can detect it; honour-system,
   with a pre-commit `git diff --quiet origin/main -- plugins/` hook as the
   next lever if it recurs.
8. **Wrap every `run_main()` call in `with ... .pushd(<tmpdir>):`.** An
   unguarded call was proven able to flip a live coordinator run to
   `handed_off`, release the partition lock, and rewrite the operator's REAL
   `pipeline-state.json` (MAR-177). **Enforced** by
   `tests/acs/test_testing_conventions_guard.py` (detector 2, a
   staleness-checked allowlist of 7 legitimately-exempt sites).
9. **Never assert the absence of an artifact the code under test never
   creates.** This shape recurred across MAR-175, MAR-172, MAR-169 and
   MAR-177 — six sites in total. **Enforced** by
   `tests/acs/test_testing_conventions_guard.py` (detector 3, which resolves
   the module under test and abstains rather than guesses when it cannot).

## Roadmap to close the gap (prioritized by value ÷ cost)

1. **Schema-validate produced artifacts** *(cheap, broad, mostly free).* Add a
   harness helper that validates any workspace JSON against its schema; call it
   in every artifact scenario and in the deterministic seeds. Turns "is the
   output good?" into "is it well-formed and complete?" — deterministically.
2. **Coverage matrix + guardrail** *(cheap).* Keep the table above current and
   add a contract test that fails if a new skill ships without at least a
   trigger eval, so coverage cannot silently regress — the guardrail already
   has two live instances to close: `create-requirements` and `docs-sync`
   both shipped with no trigger eval (see the Trigger column above).
3. **Fill critical-path artifact evals** *(paid, pre-release).* In order:
   `docs-sync`/`code` (real run), a **forge tier** for `create-pr` + `merge-pr`
   (throwaway GitHub repo — foundation delivered by MAR-67: harness + config +
   guards + teardown; `create-pr`'s scenario shipped in MAR-68
   (`create_pr_forge`), so one scenario (`merge_pr_forge`, MAR-69) and the
   onboarded target repo remain), then `ship` end-to-end — covering the
   delivery spine.
4. **LLM-as-judge for subjective skills** *(paid).* Rubric-scored evals for
   `create-prd` / `create-architecture` / `create-design`, whose quality is
   about content soundness rather than artifact shape.
5. **Dogfooding as standing coverage (E3).** Every acs change shipped via
   `/acs:ship` is a real behavioral test; per-ticket metrics surface regressions.

## G13 e2e-integrity validation

PRD **G13** ("Enforceable e2e integrity") is validated **read-only** from
artifacts `/acs:merge-pr` and `/acs:code` already produce (Decision E1,
first run 2026-07-12 as MAR-127 — [ADR 0049](../adr/0049-e2e-3-read-only-g13-metric-validation.md)) —
no standing dashboard panel, no new mechanism.

**Re-run procedure, each release:**

1. **Sub-metric (a)** — "0 PRs merged with a red e2e suite while the gate is
   enabled." Read `states.readiness.ci` from every merged ticket's
   `<partition>/phases/merge-pr/result.json` this release, and cross-check
   whether `"E2E suite"` is a required context via `gh api
   repos/<owner>/<repo>/branches/<default_branch>/protection --jq
   .required_status_checks.contexts`. Count merges where `ci` was red while
   that context was required. If the context is absent, there is no
   gate-enabled window and the count holds **vacuously**, not against a real
   population — record that honestly rather than as an unqualified pass.
2. **Sub-metric (b)** — "100% of user-facing-surface specs declare e2e
   impact." Enumerate merged tickets whose changeset touches a user-facing /
   cross-component surface this release, and confirm each `specs/*.md` Test
   plan declares e2e impact or an explicit "no e2e impact" reason — already
   enforced live by the `code-verifier`'s existing e2e-impact dimension (no
   new mechanism read here). Record the ratio and the enumerated ticket list.

**Latest recorded result:** see the "First validated" annotation on PRD
G13's line in [prd.md](../product/prd.md).

## See also

- [evals/README.md](../../evals/README.md) — the harness, cost tiers, how to add a scenario
- [tests/](../../tests/) — the deterministic + contract suites
- [docs/product/roadmap.md](../product/roadmap.md) — Epic **E1** (eval harness) and **E3** (dogfood)
