# LLD — Interface contracts

The binding shapes live in machine-validated files; this page is the index.
Canonical detail: `plugins/acs/docs/INTERNALS.md`.

## Coordinator ↔ subagent (JSON, `plugins/acs/schemas/`)

| Message | Direction | Key content |
|---------|-----------|-------------|
| the task document | coordinator → subagent | skill, step, run id, iteration; objective, input file refs, constraints, context (clarifications, prior findings) |
| the result document | subagent → coordinator (final message, nothing after) | status, output file refs (incl. the iteration artifact), findings, errors, questions |
| the handoff | step coordinator → /ship | ≤ ~1 KB summary, artifact refs, next step, questions on `needs_input` |

**Messages are JSON, validated in the hook.** The XSD layer —
`acs-messages.xsd` and the `validate_xml.py` that enforced it — is removed in
v0.5.0: a second schema language bought nothing the first one did not already
carry, and the in-process XML validator existed only to avoid a subprocess per
message. The contract's declarations are now the fifteen JSON Schemas under
`plugins/acs/schemas/`, `result.schema.json` among them, and `acs.py result
validate` checks a step's result document before its post-hook consumes it.
Constraint names stay typed — a misspelled delegation key fails at the
coordinator rather than arriving at the subagent as an absent value.

**`<metrics>` removed (MAR-1, ADR 0082).** The self-estimated
`<metrics tokens-input=".." tokens-output=".." cost-usd="..">` element is
gone from the result document's shape — `result.schema.json` does not declare
it, so a stray token/cost field is rejected as an undeclared property. Token
and cost figures are no longer part of the
subagent-to-coordinator message contract at all; they are measured from the
run's own transcript and the statusLine cost sample at `finalize_run` time
(see the Run-entry / totals contract below).

## Run-entry / totals contract (MAR-1, ADR 0082)

`finalize_run` no longer trusts a coordinator-supplied `tokens`/`cost_usd`
self-estimate. A `<skill>-state.json` `runs[]` item now carries, additive to
the existing `started_at`/`ended_at`/`status`/`stop_reason`/`handoff_summary`
shape:

| Field | Shape | Meaning |
|---|---|---|
| `session_id`, `transcript_path` | nullable string | Captured off the `PreToolUse(Skill)` envelope by the session marker, threaded on at `acs.py step start`; `null` when no marker was accepted |
| `checkout_id` | nullable string | Needed at finalize time to locate this checkout's cost-sample/cursor files |
| `tokens.{input,output,cache_creation,cache_read}` | integers | Raw measured token counts (`tokens` widens its explicit allow-list under `additionalProperties: false`) |
| `cost_usd` | number or `null` | `null` means `cost_basis="unavailable"` — never a fabricated `0` |
| `cost_basis` | enum | `measured` / `apportioned` / `unavailable` |
| `cost_scope` | enum | `session_total` / `main_session_only` on a charge; `no_unconsumed_sample_in_window` / `cost_total_reset` reused as the degraded reason when `cost_usd` is `null` |
| `excluded_cost_usd`, `excluded_token_share` | number or `null` | The unattributed same-window slice dropped from the ticket's cost, per C-8 — never redistributed onto attributed roles |
| `role_usage` | array | Per-role `{role, input, output, cache_creation, cache_read, cost_usd, cost_basis}` buckets, including a first-class `coordinator` bucket and an `unattributed` bucket that never receives a dollar share |
| `model_usage` | array | Per-model `{model, input, output, cache_creation, cache_read, cost_usd, cost_basis}` buckets — parallel to `role_usage`, unattributed-inclusive (D1.1 Option B). `cost_usd` apportions the run's FULL charged delta by token share with no unattributed exclusion (D1.2 Option A), so `sum(model_usage.cost_usd)` can exceed `sum(role_usage.cost_usd)`'s attributed-only total by `excluded_cost_usd` — a named, testable reconciliation identity, not a bug. |

`run.json`/`metrics.json` `totals` gain four additive counters —
`runs_timed`/`runs_untimed` and `runs_cost_measured`/`runs_cost_unavailable`
— incremented for every run regardless of whether it contributes to the
`working_seconds`/`cost_usd` sums; a run with a `None`-elapsed interval or a
non-measured/apportioned `cost_basis` (including a legacy run with no
`cost_basis` field at all) is excluded from those sums but still counted, so
averages never divide by the wrong denominator. `totals.tokens` also widens
the same way as the run-entry `tokens` field above — from `{input, output}`
to `{input, output, cache_creation, cache_read}` — summed by
`compute_ticket_totals`/`update_metrics` across all four classes. All of this
is schema-additive — no previously valid state/pipeline/metrics document
becomes invalid.

## Coordinator ↔ deterministic layer (CLI)

| Helper | Contract |
|--------|----------|
| `acs.py step start --step S [--ticket\|--args\|--allocate [--seed-next N]]` | stdout: context JSON (settings, run dir, subject, models, reconcile/handoff, post_hook path); records the step `in_progress`, takes the lock, writes the checkout pointer. `--step` is validated against the resolved workflow, not a closed enum. `--allocate` on a fresh/unreconciled `(repo_id, prefix)` partition (MAR-402): `allocate_ticket_id`'s fail-closed reconciliation gate refuses with **exit 2** and actionable stderr naming the ranked local-evidence proposal and the exact `--seed-next <n>` recovery command — no id minted, no lock/pointer/run-entry left behind. `--seed-next N` confirms the proposal (or repairs a wrong/stuck reconciliation) and mints `<PREFIX>-N`; `--seed-next` without `--allocate` is a malformed invocation, exit 2 per the file's existing stderr idiom |
| `post-<skill>.py --ticket T --result-file F` (or stdin JSON) | input: the **result document** `{status, stop_reason, states, findings, errors, tokens, cost_usd[, handoff_summary]}`; finalizes run + ledger + index + metrics, releases lock; exit 0 on success, **exit 1** (not 2) when the `--result-file` is missing or not a JSON object, stdin JSON is malformed, the context cannot be built, the ticket id cannot be resolved, or no active partition exists — a post-hook records, it does not gate. **MAR-1/ADR 0082**: `tokens`/`cost_usd` on this input are vestigial — `finalize_run` measures both from the run's transcript/statusLine sample instead and silently ignores a coordinator-supplied value, a soft landing rather than a rejection |
| `new-ticket.py --title --type [--parent --needs-design --docs-only --size --stakes … --seed-next N]` | mints id + partition + mint-time create-ticket state; epic backlinks; --size {trivial,small,standard,large} and --stakes {low,normal,high} write classification axes + derived lane. On a fresh/unreconciled `(repo_id, prefix)` partition (MAR-402): the same `allocate_ticket_id` fail-closed reconciliation gate refuses with **exit 2** and actionable stderr naming the local-evidence proposal and the exact `--seed-next <n>` recovery command — no ticket, partition, or `ticket.json` written. `--seed-next N` confirms/repairs the floor and mints `<PREFIX>-N` |
| `clarify.py add\|answer\|list` | the Q&A ledger (`clarifications.json`); assumptions need `--rationale` |
| `handoff.py --summary` | finalizes the in-flight step `interrupted` with `stop_reason: context_pressure`, releases the lock, prints `continue_with` |
| `codeowners.py resolve --repo-root --changed-files [--codeowners-path]` | stdout: `{source, owners[], reason}`; exit 0 on all data outcomes, exit 2 on malformed invocation |
| `stacked-base.py check --base B --commit-message-format F --ticket-prefix P [--repo-root P]` | stdout: one compact JSON object — `verdict` (`clean`\|`own_violations`\|`stacked_base`), `base_ref`, `merge_base`, `range`, `checked`, `stacked[]`, `own[]`, `ignored[]`, `notes[]`, `message`, plus `replay_onto` **only when `stacked` is non-empty**; **exit 1** on verdict `stacked_base` — a *verdict*, neither a failure nor a finding, and the one signal `/acs:create-pr` stops its step-1 run on, before the push; **exit 2** when the condition cannot be evaluated at all (the base ref does not resolve, or the histories share no merge base) with `acs stacked-base: <reason>` on stderr and **no stdout at all** — the JSON object is printed on exits 0 and 1 only. Read-only and network-free: every tree test runs against a throwaway `GIT_INDEX_FILE` under `tempfile.mkdtemp()`, nothing under `.git` is written, and the caller performs the `git fetch`. A non-empty `notes` qualifies the report — `message` accounts for every entry, each named exactly once — so a qualified exit 0 is advisory, never a settled result |
| `mermaid_lint.py FILE.md [FILE.md ...]` | stderr: `source:line: [rule] message` per finding; exit 1 on any finding, exit 0 clean, exit 2 on usage error or unreadable file; also importable — `lint_text(text, source="<text>")`, `lint_file(path)`, `Finding(source, line, rule, message)` |
| `structure_lint.py --sections "A; B; C" [--ordered] DOC.md` | stderr: `source:line: [rule] message` per finding; exit 1 on any finding, exit 0 clean, exit 2 on usage error or unreadable file; `--sections` is `;`-delimited (a name containing `&` is not split); also importable — `lint_structure(text, sections, ordered=True, source="<text>")`, `lint_file(path, sections, ordered=True)`, `Finding(source, line, rule, message)` (same 4-field shape as `mermaid_lint.Finding`) |
| `citation_check.py --plan <plan.md> --root <name>=<path> [--root …]` | stdout: one JSON line per resolved citation — `{claim, path, line, excerpt}`, where `line` is the citation's line in the **plan** file, never a locus in the cited file; stderr: `source:line: [rule] message` per finding (`citation-unresolved`, `citation-excerpt-not-found`, `citation-inventory-empty`); exit 1 on any finding, exit 0 clean (≥ 1 citation, all resolved and excerpt-matched), exit 2 on usage error or an unreadable plan file; also importable — `extract_citations(text, heading=…)`, `resolve_and_check(citations, roots, plan_path)`, `Finding(source, line, rule, message)` (same 4-field shape as `structure_lint.Finding`) |
| `prd_conformance_check.py --plan <iter-n-plan.md> --mode {greenfield\|brownfield\|amend} --repo-root <repo-root> --clarifications <partition>/clarifications.json --prd <prd> --roadmap <roadmap> [--added-heading "<verbatim milestone heading>" ...]` | stdout: one JSON line per manifest entry, each carrying a `"family"` key (`code-evidence`\|`answer-fidelity`\|`roadmap-outline`) alongside the `citation_check`-shaped fields for its family; stderr: `source:line: [rule] message` per finding (`code-citation-unresolved`, `code-citation-excerpt-not-found`, `code-evidence-empty`, `answer-not-dispositioned`, `answer-anchor-not-found`, `answer-anchor-file-unknown`, `roadmap-milestone-not-found`, `roadmap-milestone-unplanned`); exit 1 on any finding, exit 0 clean, exit 2 on usage error or an unreadable `--plan`/`--clarifications`/`--prd`/`--roadmap` file; also importable — `check_code_evidence(text, repo_root, plan_path)`, `check_answer_fidelity(text, clarifications, prd_text, roadmap_text, plan_path)`, `check_roadmap_milestones(text, roadmap_text, mode, added_headings, plan_path)`, each returning `(findings, manifest_entries)` in `citation_check`'s `Finding`/dict shapes; imports `citation_check.extract_citations`/`resolve_and_check` unchanged — zero re-implementation of path containment |
| `release_notes.py status\|draft\|bump --version X.Y.Z --repo-root P [--workspace W] [--dry-run] [--ticket-prefix PFX] --release-config <json>` | stdout JSON per subcommand — `status`: four idempotency signals (manifests/changelog/branch-PR/tag), now resolved against the block's `version_locations`/`changelog_path`/`tag_format`/`release_branch_format`; `draft`: authoritative `draft_section` + `{merged,covered,missing}` coverage report, each `tickets[]` entry carrying an additive `source` of `"archive"` or `"git-log"` — the merged-ticket archive is enumerated first and always wins on a duplicate id, and a `git log` fallback over `<since_tag>..<base_branch>` recovers tickets with no archive entry; `bump`: `files_changed[]` per the block's `version_locations`+`extra_refs`+`changelog_path`, atomic per-file write (temp-file + rename); `--ticket-prefix` is accepted by `draft`/`bump` only, never `status`; exit 0 on all data outcomes (incl. nothing-to-release), exit 2 on malformed invocation, unreadable/missing CHANGELOG/manifest, or a malformed/absent `--release-config` block |
| `migrate_workspace.py --from <old-workspace-root> --to <new-state-root> --repo-root <main-checkout-root> [--dry-run]` | stdout: one line per planned action (`copy-ticket`/`keep-existing`/`copy-file`/`skip-identical` `<rel-path>`), plus a final status line; exit 0 on success, "already migrated" (old root absent), or `--dry-run` (no writes); exit 2 on an unresolvable `--repo-root`, a `--from`/`--to` overlap, a preflight abort — a live `.lock` or an `in_progress` last run anywhere under `<old>/<repo-id>/` — a repo-level-file conflict where source and destination differ, or a post-copy verification failure |
| `plan-approval.py [path] [--run R] [--plan P]` | default verb `check`: stdout JSON — `{ok, eligible, plan_approved, delivery_path, failures[]}`, or `{ok, skipped:"delivery_path", …}` on `trivial`/`small`, `{ok, skipped:"unclassified", …}` on a plan with no judged path, or `{ok, skipped:"already-approved", …}` on an unchanged approved digest; writes `steps/create-impl-plan/plan-approval.json` (sole writer) and mirrors `states.plan_approved` into the plan step's state. Verb `path`: prints `{ok, run_dir, plan, delivery_path, owes{api_contract,test_cases,e2e}, contract_errors[]}` from the plan's `## Contract` block and **writes nothing** — the CLI `/acs:code` reads the path through (ADR 0001, ADR-0098). **exit 0 on every data outcome including ineligible**; **exit 2** on an unresolvable run, or a `--plan` whose realpath escapes `steps/create-impl-plan/` |

Exit codes: 0 ok; **2 blocked/invalid** — a failed gate, an unresolvable
ticket/partition, an archived ticket, a held lock, a repo-level write refused
because its `O_EXCL` guard was held for the whole budget (`GuardTimeout`, a
`GateError`: the stderr names which of the command's writes are already durable,
and any ticket lock the command took is released first), or a malformed
invocation — **unless a row above states otherwise** (`post-<skill>.py` exits 1 on the
failure arms listed in its row; `mermaid_lint.py`/`structure_lint.py`/`citation_check.py`/
`prd_conformance_check.py` exit 1 on findings, and `stacked-base.py check`
exits 1 to report the `stacked_base` verdict, which is neither a failure nor a
finding). Always with actionable stderr.

## Hook events (Claude Code)

`PreToolUse(Skill)` → `dispatch.py pre` → `acs_lib.GATES[skill]`, run
in-process under a bounded alarm that fails closed (exit 2 blocks);
`SessionEnd` → `dispatch.py session-end` (finalize `interrupted`, release lock).

## Delivery path (ADR-0095)

**The path is recorded on the PLAN, not configured on the workflow.**
`ship.yaml` has no `delivery:` block: the path is a property of the work, and
the only reader who has seen the work when the judgement is made is
`/acs:create-impl-plan`. It writes the judgement into the plan's machine-
readable `## Contract` block:

```yaml
delivery_path: standard        # trivial | small | standard | complex
delivery_path_reason: "seven files across two modules, with a schema change"
```

`acs_lib/plan_contract.py` is the reader — `delivery_path(read(plan))` — and
`/acs:code`'s pre-hook is the one caller that acts on it, dispatching to the
matching leg. `run.json` records nothing about the path: it is derivable from
an artifact the run already has, and a second copy is a second thing to keep
true.

One judgement, made once from the plan. A resumed run re-reads the plan and
reaches the same answer, so a pipeline cannot end up half on one path and half
on another without the plan itself having changed — and an edited plan is an
unapproved plan, which the deep paths' approval brake already refuses.

**What this replaced.** MAR-56 put three optional fields on `ticket.json` —
`size` (`trivial|small|standard|large`), `stakes` (`low|normal|high`) and a
`lane` cache derived from them by `derive_lane` — mirrored onto
the run ledger and `tickets-index.json`. MAR-106 added an
`escalations` array on `code-state.json` run entries, a fixed 13-field event
appended by `record_escalation_event` at an iteration-start detection point,
so that a mid-run lane change was never silent. MAR-108 added
`confirm_deescalation`, the only writer able to lower those axes, unreachable
without an *answered* `clarify.py` reference.

All of it is retired. The axes were a guess made before anyone read the code;
the escalation ledger and the de-escalation writer existed only to make that
guess safe to revise mid-run. One judgement, made from the plan and recorded
once, needs none of them. A ticket from an older build that still carries
`size`, `stakes` or `lane` is read as if it did not.

## Guard-denial audit trail (MAR-578)

`<skill>-state.json` run entries carry an additive, optional `guard_events`
array (`runs[-1].guard_events: [{...}]`), appended by `record_guard_event(tdir,
skill, event)` (`acs_lib/step.py`) — creates the list when absent, persists via
the same pretty-printed `write_json`. The state file is the denied executor's
own (`code-state.json` is the common case, not the only one): the guard records
under the active executor's skill, and the derivation below is skill-agnostic.
It returns `False` instead of raising when there is no run entry to carry the
event — its sole caller is a deny path whose verdict must not depend on the
recording. (Its retired sibling `record_escalation_event` raised there, which
was right for an audit write whose absence was itself the signal that a lane
change went unrecorded; this recorder has the opposite obligation.)

Each event is a fixed 7-field dict: `ts, skill, iteration, tool, target, reason,
declared_count` — `iteration` is a **string** (the highest declared file-map
iteration); `target` is repo-relative when the denied path sits under
`checkout_root`, else as given, and `null` for `unreadable_payload`, where no
path is nameable; `reason` is `"outside_map"`, `"control_input"`, or
`"unreadable_payload"`; `declared_count` is the declared union's size for
`outside_map` and `0` for the other two.

Two bounds hold at every deny site. An event is recorded **only on a deny** —
every fail-open branch (not a write tool, no partition, no active executor)
records nothing — and recording **never changes the verdict**: a failed append
is one extra stderr note beside the unchanged warning, with no retry, wait or
lock. The item shape **is** declared in
`plugins/acs/schemas/skill-state.schema.json` — the retired `escalations` array
never was; run-entry items already declare
`additionalProperties: true`, so that declaration documents the entry rather
than tightening what a run entry may carry.

Read path: `acs.py guard events --ticket <id> [--skill code]` prints one
pretty-printed object, `{ok, ticket_id, skill, count, events, path}`, with
`events` in the order they were denied; it exits non-zero with a message when
the partition or that skill's state file is absent. Derived surface:
`states.review.guard_denials` = `len(runs[-1].guard_events)`, computed by
`post-<skill>.py` through `acs_lib/derive.py` and **absent, not `0`**, when
nothing was denied — a run that never tripped the guard carries no key rather
than a `0` the reader cannot distinguish from a run predating the trail.

## Inter-step contract (state files)

The next skill reads only canonical `states` keys — e.g. `/create-pr` gate:
`code-state.states.verifier_passed == true`; `/merge-pr` gate: a `states.pr`
reference recorded by a COMPLETED step — `gates._pr_recorded_for` reads
`steps/<skill>/state.json` for `create-pr` and for each `DELIVERY_TICKET_SKILLS`
member, across every run of the ticket, and requires that step's last status to
be `completed`. Full table:
INTERNALS.md "Canonical states keys per skill". Schemas:
`plugins/acs/schemas/*.schema.json`. `code-state.states.plan_approved` is
recorded by `plan-approval.py` and is **not** read by any gate this
release — `/create-pr`'s gate remains `code-state.states.verifier_passed ==
true` (unchanged; MAR-73, slice 3 of MAR-69).

## Settings (consumer repo)

`.acs/settings.json` (+ gitignored `settings.local.json`, user-scope file);
per-key merge local → project → user; validated by every pre-hook
(`settings.schema.json`): `ticket_prefix`,
`test_coverage_percent`, `merge_strategy`, `e2e?`, `suites?`,
`tests?`, `enforcement?`, `models`, `tracker`, `formats`
(array of glob strings; absent key resolves to the seed default
`["auth/**","payments/**","migrations/**","public-api/**","security/**"]`).
`e2e?` is a deprecated compatibility alias, normalized at load time into
`suites["e2e"]` — new configuration should prefer `suites.e2e` directly.
`tests?` and `enforcement?` back the opt-in CI gates `/acs:setup` can scaffold
(offered at Step 2, installed by Step 3's `setup apply`):
`acs-conventions.yml`+`check-conventions.py` (`enforcement`)
and `acs-tests.yml`+`run-tests.py` (`tests`). The e2e CI-gate artifact family
(the same install, offered only when an e2e suite is configured) is the same
shape: `acs-e2e.yml` + `run-e2e.py` (the committed
template pair), built from `e2e?`/`suites?` — no dedicated settings key of
its own — and wired as the `E2E suite` required-check context.
`/acs:setup` writes only the project file, and only `ticket_prefix`, the
`formats.*` conventions and the chosen gates' keys (`tests.command`,
`enforcement.checks.commit_message`); `setup_wizard.split_defaults` drops any
answer equal to its built-in default and removes one an earlier run wrote.
Every other key is edited by hand.
No key locates the workspace or a document ([ADR-0102](../../adr/0102-documents-are-found-not-configured.md)): the
workspace is always `<main-checkout>/.acs/state-machine` (anchored via
`git rev-parse --git-common-dir`, gitignored; ADR-0086), ticket documents are
fixed at `docs/tickets/<ID>/`, and a skill finds every other repo document
through `CLAUDE.md` and the repo, creating a missing one at its `docs/`
convention. `release_notes.py --workspace` (above) is unaffected in shape —
still an absolute path argument — and its caller passes this resolved
value.
`formats.design_template` (default `design-default`) resolves identically to
`formats.pr_description_template` (built-in name → `.acs/templates/<name>.md`
→ absolute path); its section companion `enforcement.design_sections`
defaults from the configured template — the built-in default encodes today's
exact required-section list, so an absent key is byte-identical to the prior
hardcoded gate (ADR 0065). create-design's verifier enforces the resolved
list as a blocking `structure` dimension via `structure_lint.py`.
The requirements set (found in the repo, else `docs/requirements/`) has a
**functional** and a **non-functional** subfolder (`functional/` and
`non-functional/` by default; an existing set's own names are followed).
`/acs:create-requirements` is the producer skill that bootstraps or amends
the requirements set there in one of three modes — brownfield
reverse-engineer (architecture-aware feature-area enumeration with a
codebase-inventory fallback, DRAFT/code-cited; ADR 0061), greenfield elicit
(elicits behavior/quality from the user, DRAFT/answer-cited; ADR 0062), and
amend (augments only absent/ungrounded area files, preserving existing files
byte-for-byte) — each DRAFT / human-confirm-required via interactive-confirm
before write; `/acs:code`'s requirements-merge (above) continues to write
into the same model afterward. Code-cited coverage stays 100% — relocated,
never reduced — but a code-cited clause's citation(s) live in that doc's
companion `.evidence.md` sidecar, not inline in the body; the body keeps the
clause text, its stable anchor, and any C-22 `DRAFT — human-confirm-required`
marker (the sidecar convention, Decision B / ADR 0064).

Conformance chain: `PRD → architecture → principles → standards → design → code`, each level verified against the one above it.

Requirements (`docs/requirements/` by default, `functional/`+`non-functional/` subfolders) is a **living behavioral contract** that travels ALONGSIDE this chain — bootstrapped or amended by `/acs:create-requirements`, accreted by `/acs:code`'s documentation step, read by `/acs:create-ticket` as current behavior — but it is **not a verified conformance level**: no code review dimension checks a ticket's conformance against the requirements set the way each chain level is verified against the one above it (D1; ADR 0060/0061/0062). The chain line is unchanged; this note only clarifies where requirements sits relative to it.

`/create-prd`'s output contract now additionally includes the **"Release
versions"** mapping table in `roadmap.md` (one row per release version →
milestone/wave + epic(s) delivered), verified by the create-prd verifier's
0-orphan-milestone coverage sub-check (ADR 0053).

The `standards` chain level has a documentary counterpart in this repo at
`docs/standards/standards.md` (e.g. the test-file-naming standard); these
standards are enforced by guard tests and pipeline guidance rather than as a
runtime-verified conformance level.

`DOC_BOOTSTRAP_DEPENDENCIES` (`acs_lib`, declared in `acs_lib/_common.py`)
declares, per doc set, which upstream doc sets it depends on — a derived view
of `acs_lib.DOC_SETS`, the one table that says what a set is (the directory
a new set is created in, delivery-ticket title, template directory, output files with their required
sections, audience, upstream inputs, dependency edges; ADR-0094). Its sibling
views `DOC_SET_DEFAULT_DIR` and `DOC_BOOTSTRAP_SENTINEL` are keyed by
set name too, and `fanout_batches()` (`acs_lib/setup_helpers.py`) is the pure
helper `/acs:create-docs` calls, passing the sets it found already present in
the repo, to compute its eligible batches (MAR-1; the presence finding is the
coordinator's, not a disk probe — ADR-0102). The default eligible set is `DOC_BOOTSTRAP_FANOUT_V1` — every
declared set, `quality`, `operations`, `principles`, `standards` — so the
N-way case is the default path and the `candidates` argument carries a
*narrowing* request (the skill's `<set|all>` argument). Adding a fifth set is
one `DOC_SETS` row plus its templates, never a code or prose change.

Each declared dependency is either **hard** (an existing gate already enforces
it) or **soft** (prose-only, ungated) — the principles→standards edge above is
the soft case: the `standards` set degrades gracefully when `principles/` is
absent and the one precondition every set shares (checked by the skill at
Start) requires only the architecture set,
so the conformance chain's "each level verified against the one above it"
holds as a hard property everywhere except this one declared-soft edge. With
four sets, that edge is load-bearing on the default path: it is what splits
the default batches into `[[quality, operations, principles], [standards]]`
instead of one flat batch. The distinction is documented once on `DOC_SETS`
and cross-referenced from here so a reader of either doc finds the other.

`parse_doc_set_arg()` is the companion pure parser and the skill's whole
argument contract: a comma-separated list of doc sets in either spelling
(`quality` or the former leg name `create-quality`), `all` on its own (`all`
beside a set name is refused, never guessed at), or exactly one delivery-ticket
id, which resumes that set's run. It returns `candidates` (set names, or
`None` for "no argument", handed straight to `fanout_batches`), `rejected`,
`resume`, and
`notices` — the exact stderr lines, in order. A token naming no doc set refuses
the WHOLE run rather than fanning out the recognized remainder, so no requested
name is ever silently dropped. `parse_fanout_for_arg()` remains the legacy
`--for <skill>[,<skill>...]` half of the same parser, accepted for one release
and adding exactly one deprecation notice that the positional form is the
spelling now — the `test` → `run-e2e-tests` alias precedent.

`project_mode(settings, checkout_root)` (`acs_lib/setup_helpers.py`) is the
declared-data counterpart for the other half of the design-phase fold (ADR
0091): the pure helper `/acs:project` calls to choose between its two legs. It
reads `PROJECT_MODE_SETTINGS_KEY` / `PROJECT_MODE_SENTINEL` (ten
packaging/build/tooling files: `pyproject.toml`, `setup.py`, `package.json`,
`go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle`, `build.gradle.kts`,
`.pre-commit-config.yaml`, `.coveragerc`) off disk through the
`_sentinel_present` primitive — no git scan, no
heuristic, no prose inference — and returns the chosen `mode`
(`"bootstrap"` | `"standardize"`), the full `evidence` list, `present`/`absent`
names, and a one-sentence `reason` the skill states back to the user. The
partial case is deterministic and deliberate: **any** single present row means
`standardize`, so only a repo with no declared evidence at all is `bootstrap`
— failing toward the additive, idempotent leg.
