# Changelog

All notable changes to the `acs` plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases are automated: bump `version` in BOTH
`.claude-plugin/marketplace.json` and `plugins/acs/.claude-plugin/plugin.json`
to the same value, point the acs `source.ref` in `marketplace.json` at
`v<version>`, add a matching section here, and merge to `main` — the Release
workflow tags `v<version>` and publishes a GitHub release using that section as
the notes.

## [Unreleased]

### Added

- **`/acs:create-principles` skill + `principles_path` settings key
  (MAR-117).** A new product-level, triad-keeping skill that bootstraps and
  maintains the consumer `principles/` doc set — `principles.md`
  (engineering principles + rationale) — reading the PRD and the
  `architecture_path` set as upstream (principles is itself upstream of
  `standards/`), delivered as a docs-only PR on its own delivery ticket
  (`create-principles-planner`/`-executor`/`-verifier`,
  `create-principles-state.json`). `principles_path` is added to
  `settings.schema.json` (optional `string | null`, default
  `docs/principles`, mirroring `quality_path`/`operations_path`) and
  defaulted by `/acs:init`'s Step-4 batch; one new coarse template ships
  under `plugins/acs/templates/principles/`.

## [0.3.8] - 2026-07-07

### Added

- **`/acs:create-quality` skill + `quality_path` settings key (MAR-112).** A
  new product-level, triad-keeping skill that bootstraps and maintains the
  consumer `quality/` doc set — `test-strategy.md` and `coverage-policy.md`
  — reading the PRD's non-functional requirements and the `architecture_path`
  set as upstream, delivered as a docs-only PR on its own delivery ticket
  (`create-quality-planner`/`-executor`/`-verifier`, `create-quality-state.json`).
  `quality_path` is added to `settings.schema.json` (optional `string | null`,
  default `docs/quality`, mirroring `adr_path`) and defaulted by `/acs:init`'s
  Step-4 batch; two new templates ship under `plugins/acs/templates/quality/`.
- **`/acs:create-operations` skill + `operations_path` settings key (MAR-113).**
  A new product-level, triad-keeping skill that bootstraps and maintains the
  consumer `operations/` doc set — `release-process.md`, `runbooks.md`,
  `observability.md`, `incident-response.md`, and `test-scheduling.md` —
  reading the PRD's non-functional requirements and the `architecture_path`
  set as upstream, delivered as a docs-only PR on its own delivery ticket
  (`create-operations-planner`/`-executor`/`-verifier`,
  `create-operations-state.json`). `operations_path` is added to
  `settings.schema.json` (optional `string | null`, default
  `docs/operations`, mirroring `quality_path`) and defaulted by
  `/acs:init`'s Step-4 batch; five new templates ship under
  `plugins/acs/templates/operations/`.
- **`/acs:test` skill + `suites` settings key generalization (MAR-114).** A
  new unhooked, model-invocable utility skill that runs the product's
  configured test suites (all, or a `--suite`-selected subset), writes an
  auditable results artifact, and closes the loop on failures by minting,
  comment-bumping, or linking a regression ticket via direct `new-ticket.py`
  reuse. The `suites` settings key generalizes the existing `e2e` setting
  into a named-command map — `e2e` is retained as a soft-deprecated,
  load-time-normalized compatibility alias into `suites["e2e"]`, and
  `/acs:init` offers a one-time `e2e` to `suites.e2e` migration on re-run.
- **Shared ADR-0012 design-time doc-consistency step (MAR-115).** A single
  canonical analysis step, transcribed byte-identically into the planner
  phase of all six design-producing skills' planners
  (`create-prd`/`create-architecture`/`create-design`/`create-spec`/
  `create-quality`/`create-operations`): read the upstream and downstream
  doc-graph slice, detect gaps and staleness, and surface findings — the
  fixed shape `{kind: "gap"|"staleness", upstream, downstream, description,
  recommendation}` — through the existing clarification ledger; the user
  decides, the executor updates the affected docs as part of the same
  change, and the verifier confirms consistency. `create-quality-verifier`
  and `create-operations-verifier` each gain a matching sixth `consistency`
  check dimension. Internally, `plugins/acs/hooks/scripts/consistency_findings.py`
  is a new stdlib-only helper that validates a finding against this shape.
  ADR 0012 is flipped from `Proposed` to `Accepted`.

## [0.3.7] - 2026-07-06

### Added

- **`/acs:metrics` surfaces the G25 escalation metric on the delivery
  summary (MAR-109).** An additive `escalations` sub-object on the existing
  `delivery_summary` panel — no new panel key — reporting four tallies:
  total escalation events, count of fast-lane (TRIVIAL/SMALL-origin) tickets
  that escalated to ≥STANDARD (per-ticket, not per-event), de-escalation
  count, and silent-reversal count (down-direction events lacking a
  `confirmation_ref`; 0 on well-formed state). Computed from the
  `escalations` arrays already visited in the existing bounded single-pass
  workspace walk — no new state surface, no extra file read. Renders on both
  `/acs:metrics` surfaces (terminal and HTML); an absent/empty escalations
  array renders every tally as `0`, not "no data".

- **`/acs:code` gains a user-confirmed mid-flight de-escalation path, never
  automatic (MAR-108).** A new `acs_lib.py` writer, `confirm_deescalation`,
  is the only function capable of lowering a ticket's `size`/`stakes`/`lane`
  below its current confirmed value; it hard-requires a resolved, *answered*
  `clarify.py` ledger entry (an `"open"` or agent-authored `"assumed"` entry
  is refused, same as a missing one — `ValueError`, no write), recomputes
  `lane` via `derive_lane`, persists exactly like the upward path, and then
  records a `direction:"down"` audit event with a non-null `confirmation_ref`.
  It is reachable only from a boundary-only, explicitly user-confirmed
  subsection of the `/code` coordinator — never from the in-loop
  trigger-evaluation path or any subagent — so the upward-only negative
  guarantee holds for every automatic/unattended path.

- **`/acs:code`'s iteration-start escalation detection point and
  fold-boundary stage re-entry are now a formalized, contract-tested
  guarantee (MAR-107).** The shipped detection point (start of each
  iteration, after the prior verifier, before the current execute) is now
  named and tested so an escalation always lands before the next verifier
  pass; the monotone never-lowered ceiling raise, the no-restart guarantee,
  and the fast-lane-to-full-lane `create-spec` re-introduction are all
  contract-tested. Zero behavior change — no `acs_lib` function is modified.

- **`/acs:code`'s in-loop escalation now writes a durable audit-event trail
  and freezes its signal set (MAR-106).** A new `acs_lib.py` helper
  `record_escalation_event(tdir, skill, event)` appends a fixed 13-field event
  (from/to lane, from/to axes, trigger, source, ceiling before/after,
  direction, confirmation ref) to `runs[-1].escalations` on `code-state.json`,
  called from step (f) of the on-trigger escalation sequence after the
  axis/lane persistence — replacing the prior free-text coordinator note. The
  three shipped escalation triggers are normatively frozen, with the
  `high_stakes_paths` glob match as the sole deterministic, unit-tested
  signal; no new deterministic scope heuristic is introduced.

### Fixed

- **`/acs:init`'s CLAUDE.md managed-block writer (`upsert_managed_block`) now
  ends the file with exactly one trailing newline on every path, so a
  consumer `CLAUDE.md` no longer trips pre-commit's `end-of-file-fixer`
  (MAR-104).**

## [0.3.6] - 2026-07-05

### Added

- **`/acs:create-pr` requests CODEOWNERS-derived reviewers and syncs the
  remaining Project fields (MAR-103).** A new stdlib-only `codeowners.py`
  helper resolves PR reviewers from the repo's CODEOWNERS file
  (last-match-wins, team-slug-aware); the PR author is always dropped, and
  an empty or author-only result skips gracefully with an info finding
  instead of a hard failure. `/acs:create-pr` and `/acs:create-ticket` also
  sync Priority, Story Points, and Parent to the board's matching named
  Project field (fixed case-insensitive table, type-driven value mapping);
  a schema-undefined field is surfaced as an info finding, same as the
  existing Type/Status fallback.
- **`/acs:create-pr` moves the ticket's Project Status to In Review (MAR-102).**
  The tracker-metadata-fill Status-set call resolves the in-review option by
  case-insensitive name (`In Review`, then `Review`) on both the create and
  edit paths. When the board defines no such option, an info finding names
  it and how to add it; Status is left unchanged and the PR is unaffected.

## [0.3.5] - 2026-07-04

### Changed

- **`/acs:create-spec` gains a spec-time simplicity gate (MAR-88).** The
  planner evaluates each decomposition for a **materially** simpler
  alternative meeting the **same acceptance criteria**; the coordinator
  **surfaces** (never blocks) a finding for the user's **decision** —
  deconflicted from `code-verifier` dim. 12, planner-charter-only.

### Added

- **`/acs:create-pr` now sets PR assignee, ticket-type label, and GitHub
  Project membership (MAR-101).** For github-tracker-synced tickets, on both
  the create and edit paths, the PR carries assignee = PR author (via `gh`'s
  `@me`), the ticket-type label alongside `ACS` (idempotent creation), and is
  added to the configured GitHub Project with Status set; a schema-undefined
  Project field is surfaced as an info finding, not silently skipped.
  `local`/unsynced tickets are unaffected; a failed `gh` metadata call is
  surfaced as a finding and never aborts the PR.

## [0.3.4] - 2026-07-03

### Added

- **`/acs:init` offers version-pinned per-role models, per-role effort, and an
  explicit e2e choice (MAR-89).** A fresh `/acs:init` now actively offers, as
  first-class setup prompts: version-pinned model ids (`claude-opus-4-8` /
  `claude-sonnet-5`) for all four roles (planner/executor/verifier/coordinator)
  instead of only the coarse `opus`/`sonnet` tiers; per-role reasoning effort
  (`low|medium|high|xhigh|max|inherit`) as an explicit choice, including the
  coordinator-scope caveat; and the e2e suite as an explicit, candidate-detected
  offer rather than a silently-defaultable Step 4 key — so no user-settable
  configuration is reachable only by hand-editing `.acs/settings.json` (goal
  G21). Prose-only change to `init/SKILL.md` guarded by a new prose-contract
  test; no settings-schema, model-id/effort-validation, or broader guided-flow
  changes (those remain v0.4.0).

### Changed

- **`/acs:code` enforces Simplicity First + Surgical Changes restraint layer
  (MAR-2).** The code-executor's Charter gains two named authoring rules:
  **Simplicity First** (minimum code that solves the spec — no speculative
  features, no single-use abstractions, no unrequested configurability, no
  impossible-case error handling; if 200 lines can be 50, rewrite; apply the
  "would a senior engineer call this overcomplicated?" check) and **Surgical
  Changes** (every changed line traces to the spec; do not refactor or reformat
  adjacent code; only remove orphans your own change created; mention but never
  delete pre-existing dead code). The code-planner's file-map step now directs
  the minimal change surface and prohibits speculative scope. The
  code-verifier gains a new blocking **Simplicity & scope** dimension (dimension
  12) that flags overcomplication and out-of-scope edits as blocking findings
  looped back to the executor. Mirrored in the `/acs:code` SKILL doc and the
  shared requirements docs (skills.md, reflection.md). Generalizes the v0.3.1
  minimal-comment policy from comments-only to a full authoring-discipline
  contract.
- **`/acs:code`, `/acs:create-ticket`, `/acs:create-pr`, `/acs:merge-pr`
  reconcile the acs ticket id with the GitHub issue/PR (MAR-75).** Tracker
  sync now cross-references the acs ticket id and its GitHub records
  bidirectionally and GitHub-natively. `/acs:create-ticket` Step 5 stamps the
  acs ticket id on the synced issue body (`acs-ticket: {ticket_id}`, via the
  task/story/epic description templates) and fills the issue's GitHub fields —
  `ACS` + type labels, assignee when known, milestone when the repo uses one,
  and applicable Project fields (Status, Type) — surfacing, never silently
  skipping, a field the Project schema does not define. `/acs:create-pr` adds a
  native `Closes #<external.key>` bullet to the PR body's `## Ticket` section
  (so GitHub auto-links and auto-closes the issue on merge) and passes
  `--milestone` when one is used. `/acs:merge-pr`'s issue-close comment now
  carries the acs ticket id and a PR back-reference
  (`Merged {ticket_id} via PR #{pr.number} — {pr.url}`). `local`/unsynced
  tickets are unaffected; no enforced `pr_title`/`branch_name`/`commit_message`
  format string and no placeholder vocabulary changed.
- **`/acs:create-pr` renders the PR title from the tracker's native reference
  when the ticket is synced (MAR-80).** A new `{ticket_ref}` token for
  `formats.pr_title` renders `[#<issue-number>]` for a GitHub-synced ticket
  (`[<JIRA-KEY>]` for Jira) and falls back to the local acs ticket id
  (`[<ticket_id>]`) when unsynced — via a new `compute_ticket_ref` helper and a
  `--provider` flag threaded through the render-title call sites in the four
  tracker-aware skills; `branch_name` and `commit_message` stay id-based. The CI
  convention checker (`check-conventions.py`) and `acs_lib.validate_formats`
  both learn the `{ticket_ref}` token so the rendered title still passes the
  enforced conventions, and the default `pr_title` becomes
  `[{ticket_ref}] {title}`. Decisions recorded as ADRs.

### Fixed

- **`/acs:create-ticket` now syncs every fanned-out epic child to the tracker,
  not just the root ticket (MAR-84).** Epic children minted during Step 4 fan-out
  were never pushed to GitHub/Jira — Step 5's sync sequence only ever ran once,
  for the root, leaving every child's `external` `null`. Step 5 (both
  `create-ticket/SKILL.md` and `create-ticket-executor.md`) now defines a
  "tickets to sync" set (`root, unless imported` + `every child minted in Step
  4`, excluding product-flow delivery titles) and wraps the existing
  `gh`/`acli` sequence in a per-ticket loop, reusing the field-fill checklist
  verbatim for each ticket. A new stdlib-only helper,
  `plugins/acs/hooks/scripts/record-external.py`, is the deterministic write
  seam that stamps `external = {provider, key}` into one ticket's own
  `ticket.json` (and refuses, as defense in depth, to write onto a
  product-flow ticket). A per-ticket `gh`/`acli` failure is surfaced as a
  finding naming the ticket id and error and no longer aborts the rest of the
  batch — the loop continues, and the failed ticket's `external` stays `null`
  for a later retry. Product-flow delivery tickets ("Product definition
  (PRD)", "Product architecture doc set") remain unsynced by design.

## [0.3.3] - 2026-07-01

### Fixed

- **`/acs:init` now detects and auto-repairs a consumer `CLAUDE.md` that an
  earlier buggy run corrupted, and reports the repair.** v0.3.2 stopped the writer
  from *producing* a doubled block, but a repo already carrying a doubled or
  orphaned block (e.g. `2 BEGIN / 3 END` from the old `find`-based non-idempotency)
  still needed a human to hand-edit it. Step 7e now reads `CLAUDE.md` before
  writing, and when the new pure detector `acs_lib.managed_block_is_malformed`
  reports marker counts other than one `<!-- BEGIN acs-managed … -->` / one
  `<!-- END acs-managed -->`, the same `upsert_managed_block` collapses the entire
  span (first `BEGIN` → last `END`, `rfind`) to a single clean pair and
  `_strip_stray_markers` scrubs any orphan marker left in the surrounding text, so
  no doubled block or orphan `END` survives the next run. The step prints
  `repaired malformed acs-managed block in CLAUDE.md (was N BEGIN / M END -> 1/1)`
  and surfaces the repair in the completion report's Results/Findings, so a repair
  is never mistaken for a routine refresh. A first-time insert into a block-less
  `CLAUDE.md` is correctly reported as a normal write, not a repair. The heal
  preserves the user-owned content before and after the block byte-for-byte and is
  itself idempotent. Re-run `/acs:init` once to collapse any lingering corruption.

## [0.3.2] - 2026-07-01

### Fixed

- **`/acs:init` no longer writes a doubled, non-idempotent acs-managed block into
  the consumer `CLAUDE.md`.** Step 7e used to read the whole `CLAUDE.acs.md`
  template — which already ships a complete block (maintainer header + its own
  `BEGIN`/`END` markers) — and wrap it in a *second* marker pair, producing two
  `<!-- BEGIN acs-managed … -->` and two `<!-- END acs-managed -->` with the
  header sandwiched between them. Re-running degraded the file further because the
  writer located the closing marker with `find` (the inner `END`), orphaning the
  outer one. The writer now injects only the guidance **body** (new
  `acs_lib.managed_body_from_template`, which drops the header and the template's
  own markers) wrapped in exactly one pair, and `upsert_managed_block` locates the
  span with `rfind` and defensively strips any stray markers from the body. Result:
  a fresh write yields a single clean pair, re-runs are byte-identical, and a
  pre-existing doubled/legacy block self-heals to one clean pair — all while
  preserving the surrounding user-owned content byte-for-byte. Step 7e also gains a
  post-write self-check asserting a single marker pair. Re-run `/acs:init` to
  collapse an already-doubled block in an existing repo.

## [0.3.1] - 2026-06-29

### Changed

- **CLAUDE.md managed block now steers ticket work to `/acs:code` / `/acs:ship`
  and explains why hand-made PRs fail the gate.** The `/acs:init`-installed
  guidance (`CLAUDE.acs.md`) tells the assistant to implement/code a ticket via
  `/acs:code <ticket-id>` (or `/acs:ship`) and let `/acs:create-pr` open the PR,
  never a raw `gh pr create`. It makes the mechanism explicit: the pipeline
  renders the branch/title/body/label from **the project's own**
  `.acs/settings.json` formats, and the CI convention gate validates against the
  same file — so a pipeline-produced PR passes by construction while a hand-made
  one bypasses the rendering and fails. Re-run `/acs:init` to refresh the block
  in an existing repo.

- **`/acs:code` writes minimal, idea-only code comments (token discipline).**
  The code-executor now writes at most one short single-responsibility line per
  new function/class (SOLID — one unit, one job), never puts a ticket id in
  source comments or docstrings, and on edits only touches a comment the change
  actually invalidates (e.g. a changed parameter) — no re-comment passes over
  unchanged logic. Mirrored in the code-planner's documentation map and the
  `/acs:code` SKILL doc step. The `commit_message` format (which carries the
  ticket id) is unchanged.

- **Corrected stale agent-topology references to the post-MAR-60 shape.**
  `docs/requirements/overview.md` and `plugins/acs/docs/INTERNALS.md` no longer
  describe the old "27 subagents / 9 planner-executor-verifier triples" topology
  that predates apply-tier inlining (MAR-60); the counts now reflect the current
  triad-vs-inline split.

- **`/acs:code` doc-sync now reconciles factual prd.md/roadmap.md claims and
  flags intent divergence (MAR-65).** Execute step 4 is extended so the
  executor reconciles FACTUAL claims in `docs/product/prd.md` and
  `docs/product/roadmap.md` as part of the same changeset diff (agent/subagent
  counts, feature/epic shipped-vs-planned status, component topology, version
  numbers, file path references). Intent content (goals, NFR targets, scope,
  vision, requirements rationale) remains `/acs:create-prd`-owned: when a
  changeset contradicts stated intent, the executor flags the divergence in its
  execute-report `problems` field (surfaced in the coordinator result document
  and PR body) and NEVER rewrites intent content. The code-planner's
  documentation map now assesses prd/roadmap factual impact; the
  code-verifier's Documentation-consistency dimension (dimension 11) makes a
  stale factual claim a blocking finding and an intent contradiction an explicit
  flagged divergence (not a block). ADR-0007 is amended inline to record the
  extended scope, the factual-vs-intent boundary, the divergence rationale, and
  the enforcement note (status remains Accepted).

## [0.3.0] - 2026-06-28

### Added

- **Complexity-adaptive delivery — four-lane routing from size × stakes
  (MAR-56).** `/acs:create-ticket` now classifies each ticket on two
  user-confirmed axes (`size`, `stakes`) and derives a deterministic `lane`
  (`TRIVIAL` / `SMALL` / `STANDARD` / `COMPLEX`) via `derive_lane()`, persisted
  to `ticket.json`, `pipeline-state.json`, and `tickets-index.json`. The lane
  drives how much process the pipeline applies; the default is full/standard
  rigor and lighter lanes are opt-in (rigor is never silently dropped).

- **Verifier-as-gate with lane-driven verify depth (MAR-58).** acs is
  autonomous-first: the verifier subagent is the in-loop quality gate on
  *every* lane (it always runs). `verify_depth(size, stakes)` scales only the
  iteration ceiling — `light` (single pass, `VERIFY_ITERATION_CAP["light"]=1`)
  for TRIVIAL/SMALL low/normal-stakes tickets, `full` (up to 3 iterations + the
  11-dimension review + e2e when configured) for STANDARD/COMPLEX and all
  high-stakes tickets — with a high-stakes floor to `full`. The TDD/coverage
  gate runs in full in every lane and is never trimmed by depth selection.

- **Trivial/small fast-lane: spec authoring folded into `/code` (MAR-59).** On
  the TRIVIAL/SMALL lanes, `gate_code` no longer requires a standalone
  `/acs:create-spec` run or a populated `specs/` directory; spec authoring
  (with acceptance criteria mapped to tests) is folded into `/acs:code`'s plan
  phase by the code-planner, and `/acs:ship` skips the standalone create-spec
  step for those lanes. STANDARD/COMPLEX/absent/unknown lanes stay fail-closed
  on the full create-spec path. The TDD/coverage hard-fail and verifier-as-gate
  (light cap 1, no inline human gate) are preserved on the fast lane.

- **Apply-tier inlining: create-pr / merge-pr / create-ticket run inline
  (MAR-60).** The three apply-work skills run deterministic-inline (coordinator
  + at most one executor), never a planner/executor/verifier triad, in every
  lane — generalizing the proven merge-pr exempt-PR inline shape. Every
  load-bearing apply step, post-hook, and canonical `states` key is preserved;
  the six triad-keeping skills (create-spec, code, create-prd, create-design,
  create-architecture, create-project) are unchanged. ~$0.10 inline vs ~$0.70
  triad per apply step (G14/G15).

- **Mid-flight lane escalation, upward-only (MAR-57).** A ticket whose true
  size/stakes turn out higher than its classification is automatically
  escalated to a higher-rigor lane mid-run (on the first higher-stakes signal:
  a verifier finding, a touched `high_stakes_paths` glob, or an explicit
  request) — recomputing lane + verify depth via `escalate_lane()` and
  re-persisting, without restarting, and re-introducing any skipped stage.
  De-escalation is guaranteed never automatic or silent: no unattended path
  lowers a ticket's lane or authoritative size/stakes below a user-confirmed
  value (an interactive downgrade command is deferred to a later ticket).

- **`/acs:init` prompts for per-role models on a fresh init.** Model selection
  is now a first-class setup step: a Recommended preset
  (planner/verifier/coordinator = opus, executor = sonnet), Inherit-session-
  model, or Custom per role. Re-runs only ask whether to change current values.

- **Behavioral-eval coverage for all 16 skills.** The `skill_triggers` routing
  eval now covers every skill: the 14 model-invocable ones by description, and
  the 2 user-only ones (`install-hooks`, `update`) by an explicit-invocation
  probe plus a negative-routing probe that asserts `disable-model-invocation`
  is honored. A new free, deterministic `update_migration` scenario certifies
  `/acs:update`'s local logic offline — numeric semver comparison
  (installed vs latest) and the Step-6 migration checks (settings validate
  against the schema; workspace requirement enforced).

### Changed

- **PRD/roadmap reconciled to the shipped verifier-as-gate model.** The
  complexity-adaptive PRD/roadmap previously described a three-tier model that
  dropped the verifier on trivial tickets behind a human-approval gate; the
  docs now describe the autonomous-first model that actually shipped (verifier
  gates on every lane; lane-driven verify depth; no inline human-approval gate;
  PR review is the human checkpoint).

- **In-process stdlib XML validation is now the default fast path (MAR-61).**
  `validate_xml.py` now validates every message via the in-process
  `validate_structurally()` engine (pure stdlib, zero subprocess) instead of
  spawning `xmllint` per message.  `xmllint` is retained as an opt-in
  authoritative check via `ACS_XML_AUTHORITATIVE=1` (PATH-guarded; absent
  xmllint never blocks a verdict).  The in-process engine matches xmllint for
  the following covered violation classes: bad root element, missing/invalid
  attribute, bad ticket-id pattern, out-of-order children, wrong list-item tag,
  bad status/severity enum, duplicate maxOccurs=1 sequence children
  (cardinality), xs:decimal grammar for cost-usd (no exponent, no inf/nan, no
  underscores), and the closed content model — undeclared attributes (the XSD
  has no anyAttribute/wildcard) and element children inside text-only
  (xs:string) leaves are both rejected, matching xmllint.  A parity corpus
  (`TestValidators` in `tests/acs/test_acs_plugin.py`) asserts identical
  pass/fail verdicts for each of these classes across both paths.

- **`validate_batch()` / `batch_overall_ok()` — new Python-callable batch
  validation API (MAR-61 AC-4).** `validate_batch(messages)` accepts a list
  of XML message strings and returns a per-message `(ok, errors)` tuple list
  in a single call with zero subprocess spawns; `batch_overall_ok(results)`
  returns `False` when any member is invalid.  The batch API calls the
  in-process `validate_structurally()` engine and is importable directly from
  `validate_xml.py`; `main()` and the CLI are unchanged (AC-6 back-compat).

- **Clarify-batching coordinator contract (MAR-61 AC-7).** All 9 hooked
  coordinator skill bodies and `docs/requirements/skills.md` now document the
  grouped-ask rule: when ≥2 clarifications are open, the coordinator presents
  all of them in ONE grouped interaction instead of serial round-trips.  Each
  answer is recorded as its own `clarify.py add` entry (one `C-<n>` per
  question, `--source` preserved); no question may be skipped, merged, or
  auto-answered outside the existing `--source assumption --rationale "..."`
  rule.  A `TestClarifyBatchingContract` suite in `test_skill_contracts.py`
  asserts grouped-ask presence, per-question ledger-entry documentation, and
  zero-auto-answer documentation across all 9 skills.

- **`/acs:merge-pr` is now agent/model-invocable (MAR-42).** Removed
  `disable-model-invocation` from the skill; the readiness gate (CI, approvals,
  conflicts, protections) and the repo's branch protection are the merge brakes,
  by whoever invokes. Because invocation source (agent vs user) is not reliably
  detectable, an **approving review is now required for every merge** (mitigation
  m6, the require-APPROVED-for-all fallback; see
  [ADR 0028](../../docs/adr/0028-merge-pr-agent-invocable.md)) — including on
  repos that require no review. `/acs:ship` still stops at create-pr. Authorised
  by the PRD Vision amendment in MAR-45.

### Fixed

- **`acs-conventions` workflow no longer cancels its own required check (MAR-43).**
  The concurrency block previously used `cancel-in-progress: true`. When a PR is
  created with `gh pr create --label ACS`, the `pull_request` trigger fires for
  both `opened` and `labeled` near-simultaneously, producing two runs in the same
  concurrency group. The cancelled run left a non-SUCCESS conclusion on the
  required "Branch / PR / commit conventions" check, which branch protection
  treated as unmet and blocked the PR (observed as PR #96). Setting
  `cancel-in-progress: false` in both `plugins/acs/templates/ci/acs-conventions.yml`
  and `.github/workflows/acs-conventions.yml` lets all concurrent runs complete;
  GitHub records the latest run's conclusion. The per-PR concurrency group is
  retained for cross-PR isolation.

### Added

- **Two-skill metrics split: `/acs:metrics` (PM view) + `/acs:usage` (usage view) (MAR-14).**
  The former single-view `/acs:metrics` skill is split into two narrowly-scoped
  utility skills over one shared stdlib aggregator:

  - **`/acs:usage`** is a new model-invocable utility skill (skill count 15 → 16,
    unhooked) that renders the **usage view**: usage summary (total cost, total
    working time, total runs, plus four averages — avg working time per ticket and
    per merged PR, avg cost per ticket and per merged PR), cost + time per ticket
    by pipeline step with the four averages (Panel 3), and token burn by role
    (Panel 6). Backed by `metrics_aggregate.py` (shared superset) then
    `metrics_render.py --view usage`. Read-only; no network call; no config key.

  - **`/acs:metrics`** is re-scoped to the **PM view**: delivery summary (headline
    KPIs — tickets done/total, PRs merged, avg lead/cycle, coverage pass rate),
    throughput by status/type (Panel 1), pipeline funnel + distinct PRs (Panel 2),
    ISSUES (id/title/status/type/GitHub key), PROGRESS (per-epic done/total +
    burn-up visual), DEADLINE ("not set" degraded frame — deadline tracking requires
    a `due_date` ticket field, wired in Child 3 / MAR-15), coverage achieved vs
    target (Panel 4), review iterations before the verifier passed (Panel 5), and
    lead + cycle time per ticket (Panel 7). Invokes `metrics_render.py --view pm`.

  **Shared mechanism.** `metrics_aggregate.py` emits one superset JSON carrying all
  panel keys for both views (the PM union usage full set; no panel appears in both
  views). `metrics_render.py` gains four new view entrypoints —
  `render_pm_terminal`, `render_pm_html`, `render_usage_terminal`,
  `render_usage_html` — selected by the new `--view {pm,usage}` CLI flag (bare
  `metrics_render.py` with no `--view` defaults to the PM view; both skills invoke
  the renderer with the flag explicitly). The existing `render_terminal` /
  `render_html` entrypoints and `--view all` remain for back-compat.

  **DEADLINE panel** ships as a "not set" B1-compliant degraded frame in this
  release (the panel key is always present; it renders "not set" without error).
  Child 3 / MAR-15 wires real due-date data via a `due_date` field on the ticket.

- **Ticket `due_date` field + live DEADLINE panel (MAR-15).** The DEADLINE panel
  in `/acs:metrics` (PM view) now derives and displays real on-track/overdue
  status from each ticket's `due_date`:

  - **`due_date` on `ticket.json`** is a new optional ISO-8601 date field
    (`YYYY-MM-DD` or null; additive, back-compatible — existing tickets with no
    `due_date` are valid and the panel degrades gracefully to "not set").
    `/acs:create-ticket` elicits and sets `due_date`; the `--due-date` option on
    `new-ticket.py` accepts and validates the value (malformed input is rejected
    with a non-zero exit).
  - **DEADLINE panel — live derivation.** `metrics_aggregate.py` reads each
    ticket's `due_date` (from the `ticket.json` already opened per ticket) and
    derives: *overdue* when `due_date < now` and the ticket is not done;
    *on-track* otherwise.  The panel shows one row per ticket with a `due_date`,
    plus a roll-up summary.  A workspace with no parseable `due_date` on any
    ticket degrades to the "not set" state (B1 — the panel key is always
    present; no crash).  An empty workspace keeps `deadline == "no data"`.
  - **Read-only.** Aggregator and renderer write nothing; the only new write is
    `due_date` at create-ticket.  No network call; no new config key.
    Deterministic: the reference "now" is the same instant stamped into
    `meta.generated_at` (pinnable in tests); the renderer reads no clock.

  This supersedes the MAR-14 interim "not set" degraded frame.

- **Distinct-PR counting via `created_pr_numbers` + idempotent backfill (MAR-13 spec 01).**
  `prs.created` in `metrics.json` now counts **distinct PRs** rather than completed
  `create-pr` run invocations — a single PR re-triggered multiple times no longer
  inflates the metric.  `update_metrics` gains an optional `pr_number` parameter;
  when `pr_created` is truthy and `pr_number` is a positive integer not already
  recorded, it is appended to a sorted de-duped `prs.created_pr_numbers` list and
  `prs.created` is set to `len(created_pr_numbers)` (idempotent: re-runs with the
  same number are a no-op).  A one-time idempotent `backfill_distinct_pr_count`
  helper heals already-inflated history by recomputing `created_pr_numbers` from
  the distinct positive `states.pr.number` values across all active and `archive/`
  partitions; re-running it is safe and produces the same result.  The
  `created_pr_numbers` field is additive on the `prs` object (no schema break); all
  other metric paths (`tokens`, `cost_usd`, `prs.merged`, ticket counts) are
  unchanged.  No new runtime dependency; no network call.
- **Lead/cycle re-cycle hardening + per-ticket re-work count (MAR-13 spec 02).**
  Panel 7 (`metrics_aggregate.py`) now carries an explicit overlap-safe guarantee:
  `aggregate()` never raises when a ticket's `code.started_at` falls after its
  `merge-pr.ended_at` (a re-cycled or overlapping step span) — the affected
  `cycle_seconds` value renders as `"no data"` and a `meta.degraded` entry (panel 7)
  is appended; one row per ticket is always returned; nothing is written.  This
  guarantee is documented in the `_elapsed_seconds` and `_panel7_row` docstrings and
  is now covered by a dedicated cycle-inversion test
  (`test_cycle_inversion_yields_no_data`).  In addition, each Panel-7 per-ticket row
  gains a new additive `rework_count` integer field (>= 0) equal to the count of
  distinct positive PR numbers recoverable from that ticket's `create-pr-state.json`
  in the resolved partition; 0 when the file is absent, malformed, or carries no
  positive PR number.  `rework_count` is read-only (zero writes), stdlib-only, and
  is not averaged at the panel level — it is per-ticket metadata next to
  `lead_seconds` / `cycle_seconds`.  No schema break; no new config key; no network
  call.
- **Pipeline-default `CLAUDE.md` guidance + exempt non-ticket merge path (MAR-9).**
  Two changes that make the acs pipeline the *automatic* path in an installed
  repo and close the non-ticket dead end. (1) `/acs:init` gains an opt-in
  (default-on) step that writes an idempotent, marker-delimited **acs-managed
  block** into the repo's `CLAUDE.md` (from the new `templates/CLAUDE.acs.md`),
  steering every Claude session to ship via `/acs:ship` instead of a raw
  `gh pr create` — re-runs replace only the block, never the surrounding
  content. (2) `/acs:merge-pr --pr <n>` (also `#n` or a PR URL) lands a
  legitimate one-off **exempt** PR: it runs the same four readiness checks and
  branch/worktree cleanup as the ticket path but resolves no ticket, writes no
  partition/state, and skips tracker sync and archiving (bumping only the repo
  `pr_merged` metric). `skill-start.py --pr` validates the PR carries the
  configured `exempt_label` (or an `exempt_branches` head) and refuses +
  redirects to `/acs:merge-pr <ticket-id>` when the PR looks ticket-backed. The
  existing ticket-backed merge flow and every other gate are unchanged.
- **`/acs:metrics` — read-only delivery dashboard (MAR-5).** A new
  model-invocable utility skill that renders dashboard panels for the current repo —
  throughput by status/type, pipeline funnel, cost and time per ticket by step,
  coverage achieved vs target, review iterations before the verifier passed, and
  token burn by role (planner/executor/verifier). Backed by the stdlib-only
  `metrics_aggregate.py` helper, which aggregates the panels from existing
  workspace artifacts and emits one JSON object (every panel key always present;
  degradation is an in-band "no data" marker, never a missing key). The skill is
  read-only: it writes no file, makes no network call, and adds no config key.
- **Deterministic cross-surface metrics renderer (MAR-5).** Rendering is now a
  deterministic stdlib helper `metrics_render.py` that consumes the aggregate
  JSON and emits the dashboard panels on two surfaces: a Unicode block-bar
  **terminal** dashboard for the Claude Code CLI (default) and a self-contained
  **HTML** component (`--html`, inline CSS, no external fetch) handed to
  `show_widget` verbatim on Claude Desktop / claude.ai. The skill now **routes**
  (aggregate → render) instead of model-composing the layout, and the
  deterministic terminal renderer **supersedes** the former model-improvised
  Markdown-table fallback. `metrics_render.py` is stdlib-only, never imports
  `show_widget`, is read-only, and is deterministic (identical JSON in →
  byte-identical output; no clock read in render) — unit-tested to the same 90%
  coverage bar as the aggregator.
- **`/acs:metrics` delivery-flow metrics (MAR-7).** The dashboard now surfaces
  delivery-flow timing on both render surfaces: **Panel 3** gains four **averages**
  summary rows — avg working time and avg cost, each per ticket and per merged PR
  (a zero denominator renders "no data") — and a **new Panel 7 — Lead + cycle time
  per ticket** shows per-ticket **lead** (`ticket.json.created_at` → `merge-pr`
  end) and **cycle** (`code` start → `merge-pr` end) wall-clock times plus their
  averages, with humanized `d`/`h`/`m`/`s` durations. Aggregated additively in
  `metrics_aggregate.py` and rendered in `metrics_render.py` (terminal + HTML),
  read-only and deterministic, with every "no data" value rendering a present "no
  data" cell — no schema, config, or network change.

## [0.2.0] - 2026-06-14

### Added

- **`/acs:init` toolchain preflight (Step 0b).** Init now checks every external
  tool the full workflow needs up front and offers to install the missing ones
  (consent-gated, platform-aware) instead of failing mid-pipeline on a missing
  `gh` or `pre-commit`. Backed by `acs_lib.check_toolchain()` — the single
  source of truth listing `git`, `python3`, `gh`, `pre-commit`, `xmllint`,
  `acli` with kind (required | recommended | optional, bumped by tracker
  provider) and per-platform install commands — plus `acs_lib.missing_tools()`.
  The Step 8 summary now also confirms the full skill set is ready.

- **CI enforcement of acs conventions (opt-in via `/acs:init`).** A new Step 7c
  offers to scaffold repo-side enforcement so a PR that never went through
  `/acs:create-pr` is still held to the same conventions before it can merge.
  It installs:
  - `.github/workflows/acs-conventions.yml` — a `pull_request` check (re-runs on
    title/body edits and label changes) that validates **branch name**, **PR
    title**, **PR description sections**, the **`ACS` label**, and (opt-in)
    **commit-message** format.
  - `.acs/ci/check-conventions.py` — a self-contained, stdlib-only checker that
    compiles the committed `formats.*` strings into regexes (the same vocabulary
    the pipeline renders from) and reads `ticket_prefix` + `formats` from the
    committed `.acs/settings.json`; **no acs install is needed on the runner**.
    It is FAIL-CLOSED (no committed conventions → error + "run /acs:init") and
    runs in `--mode pr` (CI), `--mode pre-push`, or `--mode commit-msg` (local
    hooks) — the same checker and the same configured formats everywhere.
  - Optional **local git hooks** that enforce conventions *before* push, against
    the SAME configured `formats.*`/`enforcement.*`: `commit-msg` validates the
    commit subject against `formats.commit_message` as it is written, and
    `pre-push` validates `formats.branch_name` + the push range's commit
    subjects. Installed via the pre-commit framework (tracked, shared across the
    team) or as raw `.git/hooks/*` (per-clone). PR title/description stay CI-only
    (they don't exist until a PR is open).
  - New **`enforcement`** settings block (`schemas/settings.schema.json`):
    `checks.*` toggles, `exempt_branches` globs, `exempt_label`, `require_label`,
    and `pr_description_sections`.
- **New skill `/acs:install-hooks`** — the `pre-commit install` equivalent for
  acs: installs this clone's local `commit-msg` + `pre-push` hooks (per-clone,
  user-invoked). It ensures the `.acs/ci/` files exist (copying them from the
  plugin if needed), then installs via the pre-commit framework when the repo
  uses it or via raw git hooks otherwise. A committed `.acs/ci/install-hooks.sh`
  lets a teammate who only cloned the repo run it (`sh .acs/ci/install-hooks.sh`)
  without the acs plugin. `/acs:init` Step 7c now copies the hook scripts +
  installer into `.acs/ci/` and points at this command.
- **No-bypass gate guidance.** Because branch/title are cosmetic and the proof
  of pipeline use lives in the workspace outside the repo, the check is *mandatory
  to merge* but the real gate is a **required status check on a protected default
  branch**. Step 7c detects repo-admin (`gh api .permissions.admin`) and either
  configures branch protection via `gh api` or prints the one-time admin command,
  with a configurable **`acs-exempt` label + branch allowlist** escape hatch for
  releases and bot PRs.

## [0.1.6] - 2026-06-14

### Fixed

- `/acs:init` now reliably gitignores `<repo>/.acs/settings.local.json`. The
  Step 5 ignore step is rewritten to run on **every** init (fresh and re-run,
  even when no keys changed), so a repo first initialized by an older acs that
  has the file but no ignore rule gets retro-fixed. It uses `git check-ignore`
  instead of an exact-line `grep` (a broader existing rule like `.acs/` now
  counts as ignored, so no duplicate line is appended) and guarantees a
  trailing newline before appending so the entry can't glue onto the last line
  of an existing `.gitignore`.

## [0.1.5] - 2026-06-14

### Changed

- Unified release versioning: the marketplace catalog and the `acs` plugin now
  share **one version** and a single `v<version>` release tag. The separate
  `marketplace-v<version>` tag scheme and its workflow are retired. Cutting a
  release now bumps `version` in both `.claude-plugin/marketplace.json` and
  `plugins/acs/.claude-plugin/plugin.json` to the same value and points the acs
  `git-subdir` `source.ref` at the new `v<version>` tag; CI enforces that the
  two versions match. Existing `marketplace-v*` tags remain valid in history.

## [0.1.3] - 2026-06-13

### Changed

- **Breaking**: marketplace `name` renamed from `gms-plugins` to `gms-marketplace`.
  Existing consumers must migrate:
  1. Rename the key in `extraKnownMarketplaces` (managed settings or
     `~/.claude/settings.json`) from `"gms-plugins"` to `"gms-marketplace"`.
  2. Re-run `claude plugin install acs@gms-marketplace` (the old
     `acs@gms-plugins` reference no longer resolves).

## [0.1.2] - 2026-06-13

### Fixed

- Plugin failed to install on current Claude Code (manifest validation:
  `Unrecognized key: "displayName"`), leaving `acs@gms-marketplace` uninstallable
  even after the v0.1.1 hooks fix. Removed the unsupported `displayName` key
  from `plugin.json`; the marketplace lists the plugin by `name` +
  `description`. Caught by the M2-0 validation spike
  ([docs/product/m2-0-validation-spike.md](../../docs/product/spikes/m2-0-validation-spike.md)).

## [0.1.1] - 2026-06-13

### Fixed

- Plugin failed to load on install with "Duplicate hooks file detected"
  because `plugin.json` declared `"hooks": "./hooks/hooks.json"` — a file
  Claude Code already auto-loads by convention. Removed the redundant
  manifest key so the plugin loads cleanly on a fresh install (GMS-5).

## [0.1.0] - 2026-06-12

Initial release.

### Added

- Claude Code plugin marketplace manifest (`.claude-plugin/marketplace.json`)
  listing the `acs` plugin; install with
  `claude plugin marketplace add <github-url>`.
- 12 skills: `/acs:init`, `/acs:ship`, `/acs:handoff`, `/acs:create-prd`,
  `/acs:create-architecture`, `/acs:create-project`, `/acs:create-ticket`,
  `/acs:create-design`, `/acs:create-spec`, `/acs:code`, `/acs:create-pr`,
  `/acs:merge-pr`.
- 27 subagents: planner/executor/verifier triples for each of the 9 workflow
  and product-level skills, driving the plan -> execute -> verify reflection
  cycle (max 3 iterations).
- Hook-gated pipeline: a `PreToolUse` dispatcher plus pre/post hooks per
  hooked skill — each skill refuses to run (exit 2) until its predecessor's
  run completed, post-hooks finalize run state and release locks, and a
  `SessionEnd` safety net marks interrupted runs.
- Workspace state outside the consumer repo: per-ticket partitions
  (`ticket.json`, `pipeline-state.json`, `design.md`, `specs/`, phase
  artifacts, result documents) plus repo-level `tickets-index.json`,
  `counters.json`, `metrics.json`, per-checkout session pointers, and
  `archive/` for merged tickets.
- Helper CLIs: `skill-start.py`, `new-ticket.py`, `handoff.py`,
  `validate_xml.py` (under `hooks/scripts/`).
- JSON Schemas for every workspace document
  (`plugins/acs/schemas/*.schema.json`).
- XSD-defined XML messaging (`plugins/acs/schemas/acs-messages.xsd`):
  `task`, `result`, and `handoff` messages between coordinator and subagents.
- Description templates (`plugins/acs/templates/`): `epic-default.md`,
  `story-default.md`, `task-default.md`, `pr-default.md`.
- Unit test suite (`tests/`) and CI: tests on Python 3.9 and 3.12, JSON and
  JSON Schema validation, XSD validation, hook-script byte-compilation, and
  skill/agent frontmatter checks.
- Automated release workflow: tags `v<version>` and publishes a GitHub
  release from the matching changelog section when the plugin manifest
  version changes on `main`.

[Unreleased]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.3.4...HEAD
[0.3.4]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.3.3...v0.3.4
[0.3.1]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.1.6...v0.2.0
[0.1.6]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.1.3...v0.1.5
[0.1.3]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/globalmindsolution/gms-marketplace/releases/tag/v0.1.0
