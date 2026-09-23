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
| 2 | Deterministic layer | gates block/advance, state/locks/counters/metrics, helper CLIs | free, deterministic | Every module that imports the shared `acs_case` fixture (`tests/acs/acs_case.py`) — **23** modules; re-derive with `grep -lE "^(import|from) acs_case" tests/acs/*.py` (a bare `grep -l acs_case` over-counts: `test_testing_conventions_guard.py` and `test_coverage_measurement_config.py` mention the fixture in prose without importing it): [`test_acs_case_fixture.py`](../../tests/acs/test_acs_case_fixture.py), [`test_acs_lib_gates.py`](../../tests/acs/test_acs_lib_gates.py), [`test_acs_lib_hook_entrypoints.py`](../../tests/acs/test_acs_lib_hook_entrypoints.py), [`test_acs_lib_settings.py`](../../tests/acs/test_acs_lib_settings.py), [`test_acs_lib_state_locks.py`](../../tests/acs/test_acs_lib_state_locks.py), [`test_acs_plugin.py`](../../tests/acs/test_acs_plugin.py), [`test_clarify.py`](../../tests/acs/test_clarify.py), [`test_codeowners.py`](../../tests/acs/test_codeowners.py), [`test_doc_bootstrap_fanout_legs.py`](../../tests/acs/test_doc_bootstrap_fanout_legs.py), [`test_epic_fan_out_mode.py`](../../tests/acs/test_epic_fan_out_mode.py), [`test_handoff.py`](../../tests/acs/test_handoff.py), [`test_metrics_self_estimate_removed.py`](../../tests/acs/test_metrics_self_estimate_removed.py), [`test_needs_design_epic_only.py`](../../tests/acs/test_needs_design_epic_only.py), [`test_new_ticket.py`](../../tests/acs/test_new_ticket.py), [`test_plan_approval.py`](../../tests/acs/test_plan_approval.py), [`test_planning_skills_registry.py`](../../tests/acs/test_planning_skills_registry.py), [`test_session_marker.py`](../../tests/acs/test_session_marker.py), [`test_skill_start.py`](../../tests/acs/test_skill_start.py), [`test_ticket_id_reconciliation.py`](../../tests/acs/test_ticket_id_reconciliation.py), [`test_workspace_migrator.py`](../../tests/acs/test_workspace_migrator.py) (`test_testing_conventions_guard.py` deliberately does not import it — see its own docstring). `AcsWorkspaceCase.setUp` seeds a *reconciled* `counters.json` (MAR-402); a test that needs the reconciliation refusal calls `unreconcile()` first. | every PR |
| 3 | Static validation | JSON / JSON-Schema / XSD parse, byte-compile, version consistency | free, deterministic | [ci.yml](../../.github/workflows/ci.yml) | every PR |
| 4 | Eval-suite structure | every eval case is well-formed and every shipped skill has a routing case — caught before a paid run discovers it | free, deterministic | [`test_eval_cases.py`](../../tests/acs/test_eval_cases.py) | every PR |
| 5 | Routing evals | the *right skill fires* for a natural-language request, and internal legs do not | paid (~$0.12 a run), non-deterministic — 3 runs a case | [`plugins/acs/evals/routing/`](../../plugins/acs/evals/README.md) — 41 `claude plugin eval` cases, `--tag routing` | pre-release gate |
| 6 | Artifact evals | a *real run* writes the right workspace state | paid (costly), non-deterministic | [`plugins/acs/evals/artifacts/`](../../plugins/acs/evals/artifacts/README.md) — 2 cases, `--tag artifacts --scaffold` | on demand |
| 7 | Runtime reflection verifier | each individual run's output is correct (in-band, per-run) | part of normal use | the plan→execute→verify cycle inside every skill | every real invocation |
| 8 | Dogfooding (E3) | end-to-end quality under real use | the cost of using acs | shipping acs changes via `/acs:ship` | ongoing |
| 9 | LLM-as-judge *(not built)* | subjective quality — is the PRD/design *sound*? | paid + noisy | future | pre-release for product skills |

Layers 1–4 are free and gate every PR. Layers 5–6 are `claude plugin eval`
case files inside the plugin, at
[`plugins/acs/evals/`](../../plugins/acs/evals/README.md), in the layout the
[reference](https://code.claude.com/docs/en/plugin-evals) specifies; the
pre-release gate runs layer 4 and then layer 5, so a malformed case fails for
free before a paid run. Layer 4 exists because the eval CLI never runs in CI:
without it, the first sign of a broken case would be a paid run scoring it
zero. Layer 7 is a *runtime control*, not a test.

Until the eval-suite migration, layers 4–6 were a bespoke golden dataset, a
tier-3 session measurer and a Python behavioural harness under a root `evals/`
folder. What that harness caught that nothing now does is recorded in the
suite's README; the short version is live-GitHub (forge) coverage for
`create-pr`, and explicit `/acs:<skill>` invocations.

## Coverage today (per skill)

25 shipped skills exist under `plugins/acs/skills/` — one directory per skill.
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
[`acs_lib/_common.py:28-54`](../../plugins/acs/hooks/scripts/acs_lib/_common.py) splits them
into **19 hooked** (`PRODUCT_SKILLS` + `WORKFLOW_SKILLS` + `PLANNING_SKILLS`, each with a
`pre-*.py`/`post-*.py` pair and the subagent roles `skills/<name>/acs.yaml`
declares for it) and **9 unhooked** (`UNHOOKED_SKILLS`), plus `/acs:code`'s
four delivery-path legs, which are gated as their entry point and own neither
scripts nor agents (ADR-0095). Re-derive with `ls -1 plugins/acs/skills | wc -l`
(→ `32`) and a Python one-liner importing `acs_lib` and printing
`len(HOOKED_SKILLS)`, `len(UNHOOKED_SKILLS)` (→ `19 9`).

Each column below is a **rule**, applied mechanically — a cell is derived,
never hand-picked:

- **Structure (1)** — the skill's `SKILL.md` is asserted by
  `test_skill_contracts.py` (its `ALL_SKILLS` list at `:106`, asserted against
  the skills directory at `:141`) → 32 of 32.
- **Gate (2)** — the skill has a registered gate function in `acs_lib.GATES`
  → 19 of 19 hooked, pinned by `tests/acs/test_producer_skill_gates.py:42-47`
  (`test_all_hooked_skills_have_a_gate`, a per-hooked-skill
  `assertIn(skill, acs_lib.GATES)` loop); the 9 unhooked have none by
  construction, closed by `tests/acs/test_release_skill_registry.py:94`
  (`assertEqual(len(acs_lib.GATES), 19)` — with the loop above proving
  `GATES` ⊇ the 19 hooked skills, an equal count pins it to exactly that
  set) and `:71-72`, which separately confirms one such skill (`release`)
  is absent from `GATES`.
- **Trigger (5)** — the skill has a routing case under
  [`plugins/acs/evals/routing/`](../../plugins/acs/evals/README.md) → 32 of 32.
  This column is no longer maintained by hand: `tests/acs/test_eval_cases.py`'s
  `CoverageTest` fails when any shipped skill lacks a routing case, or any case
  names a skill that does not ship, so running that module IS the check. Its
  `UNPROBED` allowlist is empty. A case is decided by the first `Skill` tool call
  its prompt provokes, read by a `tool_used` grader with an `input_match` naming
  the skill. A case written as the explicit `/acs:<skill>` command is tagged
  `explicit` and is **not reliably observable**: the CLI can expand a typed
  command before any model turn, so no `Skill` call happens and the grader reads
  zero for a probe that routed. The old harness decided those from the session's
  registration list; nothing in the `claude plugin eval` format can see that.
  **Every shipped skill is model-invocable**: none sets
  `disable-model-invocation`. That flag is enforced by the CLI, which refuses
  the `Skill` call outright while leaving the slash command working, so it
  cannot be used to make a skill "internal" — it does the opposite. Six skills
  carried it until 2026-09-13 and each was an **internal leg** dispatched by
  its entry point with a real `Skill(acs:<leg>)` call, so while it was set,
  `/acs:create-docs` could not start one of its four doc legs and
  `/acs:project` could not start either of its two. The four doc legs were
  then folded into `/acs:create-docs` outright (ADR 0094), which is probed by
  description like any other skill. The two legs that remain —
  `create-project`, `standardize-project` — are probed by explicit command,
  for a different reason: a user invokes a leg directly to resume an
  interrupted delivery ticket, so that command must keep resolving. What
  steers a plain description to the entry point instead is the leg's
  **description** ("Internal leg of /acs:<entry>, not a user-facing
  command"), and the `negative` routing cases measure exactly that.
  `tests/acs/test_skill_contracts.py` now fails if any skill a `Skill(acs:…)`
  call names is made non-invocable again.
- **Artifact (6)** — an artifact case under
  [`plugins/acs/evals/artifacts/`](../../plugins/acs/evals/artifacts/README.md)
  asserts that skill's own workspace state → 2 of 32: `create-ticket`
  (`create-ticket-artifacts`) and `code` (`resume-and-verify`). Both are marked
  † below: their seeds are verified by hand, but neither case has yet completed
  end to end — in the container this suite was built in, Bash is non-functional
  inside an eval run. `create-pr` used to carry a forge-tier scenario against a
  live GitHub remote; it went with the behavioural harness, and the eval
  sandbox's network rules cannot reach GitHub, so it has no replacement.

**Hooked (12)**

| Skill | Structure (1) | Gate (2) | Trigger (5) | Artifact (6) |
|-------|:---:|:---:|:---:|:---:|
| `create-prd` | ✅ | ✅ | ✅ | — |
| `create-architecture` | ✅ | ✅ | ✅ | — |
| `create-project` | ✅ | ✅ | ✅ | — |
| `create-docs` | ✅ | ✅ | ✅ | — |
| `create-requirements` | ✅ | ✅ | ✅ | — |
| `create-ticket` | ✅ | ✅ | ✅ | ✅† |
| `create-design` | ✅ | ✅ | ✅ | — |
| `code` | ✅ | ✅ | ✅ | ✅† |
| `docs-sync` | ✅ | ✅ | ✅ | — |
| `create-pr` | ✅ | ✅ | ✅ | — |
| `merge-pr` | ✅ | ✅ | ✅ | — |
| `standardize-project` | ✅ | ✅ | ✅ | — |

† the case exists and its seed is verified, but it has not yet completed end to
end (see "Artifact (6)" above).

The row set in these two tables predates several skill additions and removals
(it lists the deleted `test` alias, lists `create-docs` twice, and omits
`analyze-requirements`, `review-code`, `create-impl-plan` and others). That drift
is older than the eval-suite change and is not fixed here. For the Trigger
column, trust `tests/acs/test_eval_cases.py`, which is mechanical, over the
rows, which are not.

**Unhooked (10)**

| Skill | Structure (1) | Gate (2) | Trigger (5) | Artifact (6) |
|-------|:---:|:---:|:---:|:---:|
| `setup` | ✅ | n/a (unhooked) | ✅ | — |
| `ship` | ✅ | n/a (unhooked) | ✅ | — |
| `handoff` | ✅ | n/a (unhooked) | ✅ | — |
| `update` | ✅ | n/a (unhooked) | ✅ | — |
| `install-hooks` | ✅ | n/a (unhooked) | ✅ | — |
| `metrics` | ✅ | n/a (unhooked) | ✅ | — |
| `usage` | ✅ | n/a (unhooked) | ✅ | — |
| `test` | ✅ | n/a (unhooked) | ✅ | — |
| `release` | ✅ | n/a (unhooked) | ✅ | — |
| `create-docs` | ✅ | n/a (unhooked) | ✅ | — |

`create-pr` and `merge-pr` have no artifact case, and no route to one in the
current format: both act on a live GitHub remote, which the eval sandbox's
network rules do not reach. They were covered — `create-pr` partly, since its
scenario skipped without an onboarded target — by a forge tier in the retired
behavioural harness. The other `—` cells are the gap itself.

**Structure is complete: 32 of 32** (`test_skill_contracts.py:141` pins the
on-disk set against the `ALL_SKILLS` literal at
`test_skill_contracts.py:106`, not against `acs_lib` — and no test pins this
table itself, so a new skill's row here is not enforced; see Roadmap item 2).
**Gating is complete for what can be gated: 19 of 19 hooked skills**; the other
11 are n/a by construction — no `pre-*.py`/`GATES` entry exists for them, and
none should. **Routing covers 32 of 32** — 40 routing cases in all (26 by
description, 8 by explicit command, 6 negative) plus one off-domain control,
and `tests/acs/test_eval_cases.py` fails the build if a shipped skill loses its
case. **The gap is behavioral (artifact) coverage: 2 of 32 skills**
(`create-ticket`, `code`), and neither has yet completed end to end — so the
*common* skill bugs (a missing script reference, a malformed completion report,
a broken gate, the wrong skill firing) are already caught cheaply for nearly the
whole surface, while whether a skill produced the *right* output mostly is not.

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
5. **Cost-aware tiering.** Free tiers gate every commit/PR; the
   **pre-release gate** runs the free eval-structure check and then the paid
   routing suite, in that order, with a `--max-cost-usd` ceiling. Artifact
   cases are an on-demand tool. Never put paid evals on a per-commit or
   scheduled path.
6. **Never assert equality or ordering on an `updated_at` value.**
   `acs_lib.now_iso()` is second-resolution (`acs_lib/_common.py`); such an
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
   unguarded call was proven able to flip a live coordinator's step to a
   terminal status, release the run's lock, and rewrite the operator's REAL
   run ledger (MAR-177). **Enforced** by
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
   trigger eval, so coverage cannot silently regress — the Trigger column is
   complete today (MAR-575 closed its last three gaps), which is exactly the
   state a guardrail exists to hold.
3. **Fill critical-path artifact evals** *(paid, pre-release).* First,
   validate the two artifact cases that exist on a host where an eval run's
   Bash works. Then `docs-sync`, then `ship` end-to-end — covering the delivery
   spine. `create-pr` and `merge-pr` act on a live GitHub remote, which the
   eval sandbox cannot reach; the retired harness's forge tier (MAR-67/68) was
   the only route, and it has no equivalent in the current format.
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
   enforced live by `/acs:review-code`'s existing e2e-impact dimension (no
   new mechanism read here). Record the ratio and the enumerated ticket list.

**Latest recorded result:** see the "First validated" annotation on PRD
G13's line in [prd.md](../product/prd.md).

## See also

- [plugins/acs/evals/README.md](../../plugins/acs/evals/README.md) — the eval suite: running it, tags, grading, known limits
- [tests/](../../tests/) — the deterministic + contract suites
- [docs/product/roadmap.md](../product/roadmap.md) — Epic **E1** (eval harness) and **E3** (dogfood)
