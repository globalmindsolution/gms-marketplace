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
message. The contract's declarations are now the fourteen JSON Schemas under
`plugins/acs/schemas/`, `result.schema.json` among them, and `acs.py result
validate` checks a step's result document before its post-hook consumes it.
Constraint names stay typed — a misspelled delegation key fails at the
coordinator rather than arriving at the subagent as an absent value.

**No usage in the message contract.** The self-estimated `<metrics>`
element is gone from the result document's shape — `result.schema.json` does
not declare it, so a stray `<metrics>` element is rejected as an undeclared
property. The flat `tokens`, `role_usage`, `model_usage`, `cost_usd`,
`cost_basis` and `api_duration_ms` keys are legacy: accepted so an older
coordinator's result still validates, and ignored. Nothing measures usage in
their place either — acs records no token count, no dollar figure and no
`run.json` `totals`
([ADR 0104](../adr/0104-no-usage-dashboards-no-usage-recording.md)).

## Coordinator ↔ deterministic layer (CLI)

| Helper | Contract |
|--------|----------|
| `acs.py step start --step S [--ticket\|--args\|--allocate [--seed-next N]]` | stdout: context JSON (settings, run dir, subject, models, reconcile/handoff, post_hook path); records the step `in_progress`, takes the lock, writes the checkout pointer, and on the run's first start writes `baseline.json` (ADR-0127); `--allocate` is `/acs:create-ticket`'s alone, and `create-prd`/`create-architecture` start a ticketless run from `--args`; **refused** while a step of ANOTHER stage is `in_progress` (invariant I1 — the members of one parallel group may be open together, nothing else, ADR-0110). `--step` is validated against the resolved workflow, not a closed enum. `--allocate` on a fresh/unreconciled `(repo_id, prefix)` partition (MAR-402): `allocate_ticket_id`'s fail-closed reconciliation gate refuses with **exit 2** and actionable stderr naming the ranked local-evidence proposal and the exact `--seed-next <n>` recovery command — no id minted, no lock/pointer/run-entry left behind. `--seed-next N` confirms the proposal (or repairs a wrong/stuck reconciliation) and mints `<PREFIX>-N`; `--seed-next` without `--allocate` is a malformed invocation, exit 2 per the file's existing stderr idiom |
| `acs.py changes snapshot` / `acs.py changes diff [--since T] [--name-only\|--stat\|--patch] [--run R]` | `snapshot`: stdout `{ok, tree}` — a git tree id of the whole working tree, untracked non-ignored files included, built in a throwaway `GIT_INDEX_FILE` (the real index and tree untouched); the verdict's `reviewed_sha` holds one. `diff`: `<since>` (default: the run baseline's `base_sha`) → a fresh snapshot, the baseline's already-dirty paths excluded unless they changed again; `--name-only` prints `{files: [{path, status}]}` (ADR-0127) |
| `acs.py pr plan-commits [--ticket ID] [--run R] [--out F]` / `acs.py pr commit --plan F` | `plan-commits`: stdout `{mode, branch, base, groups: [{id, subject, layer, paths}], left_out, excluded}` — deterministic: `recorded` mode from the run's recorded results ∩ the changeset; `uncommitted` mode (a prompt run whose steps recorded nothing) every uncommitted change against HEAD, grouped by layer — documents by doc set, then tests, then code. `commit`: switches to the plan's branch when not on it, then `git add -- <paths>` + `git commit` per group; refuses a path outside the changeset, an empty group and the default branch's name; never pushes (ADR-0127) |
| `acs.py run next [--run R]` | stdout: `{ok, run_id, next, due, parallel, status, done}` — `next` is the derived cursor (the first step not `completed`), `due` every unfinished step of the cursor's stage (`[next]` for a plain step, each unfinished member for a parallel group), `parallel` true when `due` holds more than one; `done` once the cursor is `null`. Reads only; exit 2 when no run resolves |
| `acs.py notes merge --out F IN [IN ...]` | joins a parallel fan-out's slice files (survey `authoring-<id>.md`, judge `<role>-<id>.md`) into the one file downstream readers expect: markdown merged by `## ` heading — the first input's preamble, each H2 once in first-seen order, each input's body in input order behind `<!-- slice: <id> -->`; headings inside fenced code are body. Slice ids are each stem minus the prefix every input shares. stdout: `{ok, out, sections, inputs}`; **exit 2** when any input is missing (a missing slice is a failed slice) or none is named; writes `F` atomically |
| `post-<skill>.py --ticket T --result-file F` (or stdin JSON) | input: the **result document** `{status, stop_reason, states, findings, errors[, handoff_summary]}`; finalizes run + ledger + index, releases lock; exit 0 on success, **exit 1** (not 2) when the `--result-file` is missing or not a JSON object, stdin JSON is malformed, the context cannot be built, the ticket id cannot be resolved, or no active partition exists — a post-hook records, it does not gate. `tokens`, `role_usage`, `model_usage`, `cost_usd`, `cost_basis` and `api_duration_ms` on this input are legacy — accepted so an older coordinator's result still validates, and ignored: no usage is recorded (ADR 0104) |
| `new-ticket.py --title --type [--parent --needs-design --docs-only --size --stakes … --seed-next N]` | mints id + partition + mint-time create-ticket state; epic backlinks; --size {trivial,small,standard,large} and --stakes {low,normal,high} write classification axes + derived lane. On a fresh/unreconciled `(repo_id, prefix)` partition (MAR-402): the same `allocate_ticket_id` fail-closed reconciliation gate refuses with **exit 2** and actionable stderr naming the local-evidence proposal and the exact `--seed-next <n>` recovery command — no ticket, partition, or `ticket.json` written. `--seed-next N` confirms/repairs the floor and mints `<PREFIX>-N` |
| `clarify.py add\|answer\|list` | the Q&A ledger (`clarifications.json`); assumptions need `--rationale` |
| `handoff.py --summary` | the session pause (context pressure), not the `/acs:handoff` skill: finalizes the in-flight step `interrupted` with `stop_reason: context_pressure`, releases the lock, prints `continue_with` |
| `acs.py handoff send --ticket ID [--note TEXT\|--note-file F] [--attach PATH]… [--replace] [--dry-run] [--remote NAME]` / `acs.py handoff receive ID\|--ticket ID [--replace] [--keep-ref] [--remote NAME]` / `acs.py handoff list [--details] [--remote NAME]` | the team handoff (ADR-0131), over `git` to the remote (default `origin`). `send`: one commit on `baseline.base_sha` (HEAD when none) built through a temporary index — `work/` (the uncommitted work), `acs/ticket/` and `acs/run/` (the resume set, absolute paths as tokens), `attachments/` (`--attach` only), `note.md`, `manifest.json` (`schemas/handoff-manifest.schema.json`), `trees/<id>` — pushed with a lease to `refs/acs/handoff/<ID>`; refuses an existing ref without `--replace`, an archived ticket and a ticketless run; local state untouched; `--dry-run` builds nothing. `receive`: validates the manifest; refuses an existing local run or ticket without `--replace` (backed up first) and a dirty tree; dry-runs `git apply --3way` in a temporary index (conflicts listed, checkout untouched), then applies; restores the resume set with local paths, upserts the indexes, raises `counters.next`, points the checkout at the run, keeps `refs/acs/received/<ID>` locally and deletes the remote ref unless `--keep-ref`; prints `continue_with`. `list`: the refs under `refs/acs/handoff/` (`--details`: sender, time, note) |
| `codeowners.py resolve --repo-root --changed-files [--codeowners-path]` | stdout: `{source, owners[], reason}`; exit 0 on all data outcomes, exit 2 on malformed invocation |
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
`prd_conformance_check.py` exit 1 on findings). Always with actionable stderr.

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
the same pretty-printed `write_json`. The state file is the denied writer's
step's own (`code-state.json` is the common case, not the only one): the guard
records under the skill of the active `write`-kind agent, and the derivation
below is skill-agnostic.
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
every fail-open branch (not a write tool, no partition, no active write-kind agent)
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
`steps/review-code/state.json`'s `states.verifier_passed == true`; `/merge-pr` gate: a `states.pr`
reference recorded by a COMPLETED step — `gates._pr_recorded_for` reads
`steps/<skill>/state.json` for `create-pr` (and for each `DELIVERY_TICKET_SKILLS`
member — an empty list since ADR-0127), across every run of the ticket, and requires that step's last status to
be `completed`. Full table:
INTERNALS.md "Canonical states keys per skill". Schemas:
`plugins/acs/schemas/*.schema.json`. `code-state.states.plan_approved` is
recorded by `plan-approval.py` and is **not** read by any gate this
release — `/create-pr`'s gate remains the review's `states.verifier_passed ==
true` (MAR-73, slice 3 of MAR-69).

## Settings (consumer repo)

`.acs/settings.json` (+ gitignored `settings.local.json`, user-scope file);
per-key merge local → project → user over `DEFAULT_SETTINGS`; every file is
optional — with none, every key resolves to its default and no pre-hook
refuses ([ADR-0105](../adr/0105-acs-runs-without-setup.md)); validated by
every pre-hook, which still refuses a malformed value
(`settings.schema.json`): `ticket_prefix` (default `ACS`),
`merge_strategy`, `tests`, `workflow`, `models`, `tracker`, `release?`
(plus a tolerated `evals` object that nothing reads).
`tests` is `{coverage?, unit?, e2e?, <name>?}`: `coverage` is the TDD target and
CI-gate floor (default 90, exported to the gate as `ACS_COVERAGE`), `unit` is the
CI tests-gate suite (`{command, setup?}`), and every other key is a named suite
`{command, setup?, teardown?}` — the end-to-end suite is `tests.e2e`. The old
top-level `test_coverage_percent`, `suites` and `e2e` keys are gone: a file that
still carries them makes every acs skill refuse to start until
`acs.py settings migrate [--write]` rewrites it. `tracker.provider` is `local` or
`github`; `gh` is the only tracker transport.
`models` is `models.<skill>.<role> = {model?, effort?}`: an absent skill, role or
field, or the value `inherit`, inherits the parent session; the skills and roles
are the agents the plugin ships, and `acs.py settings scaffold --write` writes the
full block ([ADR-0115](../adr/0115-models-per-skill-and-role-through-generated-agents.md)).
There is no `formats` or `enforcement` block: branch, commit and PR-title style are
the model's to follow, and what a script must parse is fixed in
`acs_lib.conventions` — the branch name `<type>/<ticket_id>-<slug>`, the
CI exemptions (`acs-exempt`, `release/*`, `dependabot/*`, `renovate/*`), the `ACS`
pipeline label and the built-in template names (a repo's
`.acs/templates/<name>.md` of the same name replaces one). A `formats`,
`enforcement` or `hook_gates` block a repo still carries is accepted and ignored.
`tests.unit` backs the opt-in CI gates `/acs:setup` can scaffold (offered at Step 2,
installed by Step 3's `setup apply`): `acs-conventions.yml`+`check-conventions.py`,
which checks one rule, that the PR description names its ticket
([ADR-0106](../adr/0106-ci-checks-the-ticket-link-only.md)), and
`acs-tests.yml`+`run-tests.py` (`tests.unit`). The e2e
CI-gate artifact family (the same install, offered only when an e2e suite is
configured) is the same
shape: `acs-e2e.yml` + `run-e2e.py` (the committed
template pair), built from `tests.e2e` — no dedicated settings key of
its own — and wired as the `E2E suite` required-check context.
`/acs:setup` is optional; it writes only the project file, and only the gates'
keys (`tests.unit.command`); `setup_wizard.split_defaults` drops any
answer equal to its built-in default and removes one an earlier run wrote.
Every other key, `ticket_prefix` included, is edited by hand.
`templates/ci/check-conventions.py` runs without the plugin, so it holds its own
copy of the few constants it checks against (a test fails when the copies differ)
and checks a repo with no settings file against them.
No key locates the workspace or a document ([ADR-0102](../adr/0102-documents-are-found-not-configured.md)): the
workspace is always `<main-checkout>/.acs/state-machine` (anchored via
`git rev-parse --git-common-dir`, ADR-0086; ignored by its own `.gitignore`
of `*`, which `write_json`/`write_text` create on the first write under it,
ADR-0105), a run's documents go one folder per phase — Discovery
`<prd_dir>/features/<feature>/`, Design `<architecture_dir>/lld/<feature>/<id>/`,
Development `docs/development/<feature>/<id>/`, the directories resolved by
`acs_lib.requirements.prd_dir`/`architecture_dir`/`development_dir`
([ADR-0128](../adr/0128-requirements-from-any-container.md)); a legacy
`docs/tickets/<ID>/` is only read — and a skill finds every other repo document
through `CLAUDE.md` and the repo, creating a missing one at its `docs/`
convention. `release_notes.py --workspace` (above) is unaffected in shape —
still an absolute path argument — and its caller passes this resolved
value.
The design template is the built-in `design-default`, or a repo's
`.acs/templates/design-default.md`; the required-section list is derived from the
template itself, so the built-in default encodes today's exact required-section
list (ADR 0065). create-design's design-reviewer enforces the resolved
list as a blocking `structure` dimension via `structure_lint.py`.
The requirements set (found in the repo, else `docs/requirements/`) has a
**functional** and a **non-functional** subfolder (`functional/` and
`non-functional/` by default; an existing set's own names are followed).
acs no longer has a producer skill that bootstraps the set
([ADR-0118](../adr/0118-discovery-design-development-phases.md) removed
`/acs:create-requirements`): a set a repo keeps is optional context its
readers use, and the documentation step's requirements merge writes into the
same model as tickets change behavior. Code-cited coverage stays 100% — relocated,
never reduced — but a code-cited clause's citation(s) live in that doc's
companion `.evidence.md` sidecar, not inline in the body; the body keeps the
clause text, its stable anchor, and any C-22 `DRAFT — human-confirm-required`
marker (the sidecar convention, Decision B / ADR 0064).

Conformance chain: `PRD → architecture → principles → standards → design → code`, each level verified against the one above it.

Requirements (`docs/requirements/` by default, `functional/`+`non-functional/` subfolders) is a **living behavioral contract** that travels ALONGSIDE this chain — kept by the repo when it keeps one, accreted by `/acs:code`'s documentation step, read by `/acs:create-ticket` as current behavior — but it is **not a verified conformance level**: no code review dimension checks a ticket's conformance against the requirements set the way each chain level is verified against the one above it (D1; ADR 0060/0061/0062). The chain line is unchanged; this note only clarifies where requirements sits relative to it.

`/create-prd`'s output contract now additionally includes the **"Release
versions"** mapping table in `roadmap.md` (one row per release version →
milestone/wave + epic(s) delivered), verified by the create-prd reviewer's
0-orphan-milestone coverage sub-check (ADR 0053).

The `standards` chain level has a documentary counterpart in this repo at
`docs/standards/standards.md` (e.g. the test-file-naming standard); these
standards are enforced by guard tests and pipeline guidance rather than as a
runtime-verified conformance level.

The principles and standards levels, and the quality and operations sets
beside the chain, are written by hand. No skill bootstraps them since
[ADR-0124](../adr/0124-remove-create-docs.md) removed `/acs:create-docs`,
and with it the `DOC_SETS` table, its fan-out helpers and its argument parser.
The skills that read a set find it where the repo keeps it (ADR-0102); a
standards reader treats an absent principles set as not applicable, never as
a block, so the chain's "each level verified against the one above it" holds
wherever both levels exist.
