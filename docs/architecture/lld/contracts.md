# LLD — Interface contracts

The binding shapes live in machine-validated files; this page is the index.
Canonical detail: `plugins/acs/docs/INTERNALS.md`.

## Coordinator ↔ subagent (XML, `plugins/acs/schemas/acs-messages.xsd`)

| Message | Direction | Key content |
|---------|-----------|-------------|
| `<task skill phase ticket-id iteration>` | coordinator → subagent | objective, `<inputs>` file refs, `<constraints>`, `<context>` (clarifications, prior findings) |
| `<result … status>` | subagent → coordinator (final message, nothing after) | `<outputs>` file refs (incl. the phase artifact), `<findings>`, `<errors>`, `<questions>`, `<metrics>` |
| `<handoff … status>` | step coordinator → /ship | ≤ ~1 KB summary, artifact refs, `<next-step>`, `<questions>` on `needs_input` |

Validation: `validate_xml.py` on every send/receive; one re-request, then fail.
By default validation runs **in-process** via `validate_structurally()` (pure
stdlib `xml.etree`, raised to XSD-equivalent coverage) — no subprocess is
spawned per message. `xmllint` is invoked only opt-in when
`ACS_XML_AUTHORITATIVE=1` AND `xmllint` is on `PATH` AND the XSD is present; its
absence never blocks a verdict. A `validate_batch()` Python API validates a list
of messages in one in-process loop (MAR-61).

## Coordinator ↔ deterministic layer (CLI)

| Helper | Contract |
|--------|----------|
| `skill-start.py --skill S [--ticket\|--args\|--allocate]` | stdout: context JSON (settings, partition, ticket, models, reconcile/handoff, post_hook path); registers `in_progress` run, lock, pointer |
| `post-<skill>.py --ticket T --result-file F` (or stdin JSON) | input: the **result document** `{status, stop_reason, states, findings, errors, tokens, cost_usd[, handoff_summary]}`; finalizes run + ledger + index + metrics, releases lock |
| `new-ticket.py --title --type [--parent --needs-design --docs-only --size --stakes …]` | mints id + partition + mint-time create-ticket state; epic backlinks; --size {trivial,small,standard,large} and --stakes {low,normal,high} write classification axes + derived lane |
| `clarify.py add\|answer\|list` | the Q&A ledger (`clarifications.json`); assumptions need `--rationale` |
| `handoff.py --summary` | finalizes `handed_off`, releases lock, prints `continue_with` |
| `codeowners.py resolve --repo-root --changed-files [--codeowners-path]` | stdout: `{source, owners[], reason}`; exit 0 on all data outcomes, exit 2 on malformed invocation |
| `mermaid_lint.py FILE.md [FILE.md ...]` | stderr: `source:line: [rule] message` per finding; exit 1 on any finding, exit 0 clean, exit 2 on usage error or unreadable file; also importable — `lint_text(text, source="<text>")`, `lint_file(path)`, `Finding(source, line, rule, message)` |
| `structure_lint.py --sections "A; B; C" [--ordered] DOC.md` | stderr: `source:line: [rule] message` per finding; exit 1 on any finding, exit 0 clean, exit 2 on usage error or unreadable file; `--sections` is `;`-delimited (a name containing `&` is not split); also importable — `lint_structure(text, sections, ordered=True, source="<text>")`, `lint_file(path, sections, ordered=True)`, `Finding(source, line, rule, message)` (same 4-field shape as `mermaid_lint.Finding`) |
| `release_notes.py status\|draft\|bump --version X.Y.Z --repo-root P [--workspace W] [--dry-run] --release-config <json>` | stdout JSON per subcommand — `status`: four idempotency signals (manifests/changelog/branch-PR/tag), now resolved against the block's `version_locations`/`changelog_path`/`tag_format`/`release_branch_format`; `draft`: authoritative `draft_section` + `{merged,covered,missing}` coverage report; `bump`: `files_changed[]` per the block's `version_locations`+`extra_refs`+`changelog_path`, atomic per-file write (temp-file + rename); exit 0 on all data outcomes (incl. nothing-to-release), exit 2 on malformed invocation, unreadable/missing CHANGELOG/manifest, or a malformed/absent `--release-config` block |

Exit codes: 0 ok; 2 blocked/invalid with actionable stderr.

## Hook events (Claude Code)

`PreToolUse(Skill)` → `dispatch.py pre` → `pre-<skill>.py` (exit 2 blocks);
`SessionEnd` → `dispatch.py session-end` (finalize `interrupted`, release lock).

## Ticket classification fields (MAR-56)

`ticket.json` carries three new optional fields (additive; legacy tickets without them remain valid):
- `size` — authoritative axis (enum: `trivial`, `small`, `standard`, `large`; default `standard` when absent)
- `stakes` — authoritative axis (enum: `low`, `normal`, `high`; default `normal` when absent)
- `lane` — derived cache, recomputable via `derive_lane(size, stakes, needs_design, type)` (enum: `TRIVIAL`, `SMALL`, `STANDARD`, `COMPLEX`; default `STANDARD`)

`pipeline-state.json` records `lane` alongside `flow` (written by `update_pipeline`).
`tickets-index.json` mirrors `lane` per entry alongside `needs_design` (written by `update_index`).

## Escalation-event audit trail (MAR-106)

`code-state.json` run entries carry an additive, optional `escalations` array
(`runs[-1].escalations: [{...}]`), appended by `record_escalation_event(tdir,
skill, event)` (`acs_lib.py`) — creates the list when absent, persists via the
existing pretty-printed `write_json`. Each event is a fixed 13-field dict:
`ts, from_lane, to_lane, from_size, from_stakes, to_size, to_stakes, trigger,
source, ceiling_before, ceiling_after, direction, confirmation_ref` —
`direction` is `"up"` or `"down"`; `trigger` is `"a"`, `"b"`, `"c"`, or
`"user_confirmed_deescalation"`; `confirmation_ref` is `null` for every
upward/automatic event. No schema file edit is required — run-entry items
already declare `additionalProperties: true`. Events are recorded at the
iteration-start **detection point** (start of each iteration, after the prior
verifier and before the current execute — MAR-107 D4); a fast-lane
(TRIVIAL/SMALL) crossing into a full lane (STANDARD/COMPLEX) triggers the
fold-boundary stage re-entry that re-introduces the skipped `create-spec`
stage before the next iteration.

`confirm_deescalation(tdir, ticket, confirmed_size, confirmed_stakes,
clarify_ref)` (`acs_lib.py`, MAR-108) is the only writer capable of lowering
`size`/`stakes`/`lane` below the ticket's current confirmed value. It hard-
requires `clarify_ref` to resolve to a `clarify.py` ledger entry with
`status == "answered"` exactly — a falsy ref, an unresolvable id, an `"open"`
entry, or an `"assumed"` entry all raise `ValueError` with no write of any
kind (ticket, pipeline, index, or escalation event). On success it recomputes
`lane` via `derive_lane` (never hand-set), persists via the same three
writers as the upward path (`save_ticket` / `update_pipeline` /
`update_index`), and only then records a `direction:"down"` event via
`record_escalation_event` with `trigger:"user_confirmed_deescalation"` and
`confirmation_ref` set to the resolved `C-<n>` id — persist-then-record,
mirroring the upward on-trigger sequence's ordering (design.md:506-518).

## Inter-step contract (state files)

The next skill reads only canonical `states` keys — e.g. `/create-pr` gate:
`code-state.states.verifier_passed == true`; `/merge-pr` gate: a `states.pr`
reference in `create-pr-state` (or the product skill's state). Full table:
INTERNALS.md "Canonical states keys per skill". Schemas:
`plugins/acs/schemas/*.schema.json`.

## Settings (consumer repo)

`.acs/settings.json` (+ gitignored `settings.local.json`, user-scope file);
per-key merge local → project → user; validated by every pre-hook
(`settings.schema.json`): `workspace_path`, `ticket_prefix`,
`test_coverage_percent`, `merge_strategy`, `prd_path`, `architecture_path`,
`requirements_path?`, `requirements_layout?`, `adr_path?`, `principles_path?`,
`standards_path?`, `quality_path?`, `operations_path?`, `e2e?`, `suites?`,
`tests?`, `enforcement?`, `models`, `tracker`, `formats`, `high_stakes_paths?`
(array of glob strings; absent key resolves to the seed default
`["auth/**","payments/**","migrations/**","public-api/**","security/**"]`).
`e2e?` is a deprecated compatibility alias, normalized at load time into
`suites["e2e"]` — new configuration should prefer `suites.e2e` directly.
`tests?` and `enforcement?` back the opt-in CI gates `/acs:init` can scaffold
(Steps 7c/7d): `acs-conventions.yml`+`check-conventions.py` (`enforcement`)
and `acs-tests.yml`+`run-tests.py` (`tests`). The e2e CI-gate artifact family
(Step 7f) is the same shape: `acs-e2e.yml` + `run-e2e.py` (the committed
template pair), built from `e2e?`/`suites?` — no dedicated settings key of
its own — and wired as the `E2E suite` required-check context.
`formats.design_template` (default `design-default`) and `formats.spec_template`
(default `spec-default`) resolve identically to `formats.pr_description_template`
(built-in name → `.acs/templates/<name>.md` → absolute path); their section
companions `enforcement.design_sections` and `enforcement.spec_sections` default
from the configured template — the built-in defaults encode today's exact
required-section lists, so an absent key is byte-identical to the prior hardcoded
gate (ADR 0065).
`requirements_path` resolves a **functional** and a **non-functional**
subfolder via `requirements_layout` (`functional_subdir`/
`non_functional_subdir`, default `"functional"`/`"non-functional"`).
`/acs:create-requirements` is the producer skill that bootstraps or amends
the requirements set at that path in one of three modes — brownfield
reverse-engineer (architecture-aware feature-area enumeration with a
codebase-inventory fallback, DRAFT/code-cited; ADR 0061), greenfield elicit
(elicits behavior/quality from the user, DRAFT/answer-cited; ADR 0062), and
amend (augments only absent/ungrounded area files, preserving existing files
byte-for-byte) — each DRAFT / human-confirm-required via interactive-confirm
before write; `/acs:code`'s requirements-merge (above) continues to write
into the same model afterward.

Conformance chain: `PRD → architecture → principles → standards → design → specs → code`, each level verified against the one above it.

Requirements (`requirements_path`, `functional/`+`non-functional/` subfolders) is a **living behavioral contract** that travels ALONGSIDE this chain — bootstrapped or amended by `/acs:create-requirements`, accreted by `/acs:code`'s documentation step, read by `/acs:create-ticket`/`/acs:create-spec` as current behavior — but it is **not a verified conformance level**: no create-spec or code-verifier dimension checks a ticket's conformance against the requirements set the way each chain level is verified against the one above it (D1; ADR 0060/0061/0062). The chain line is unchanged; this note only clarifies where requirements sits relative to it.

`/create-prd`'s output contract now additionally includes the **"Release
versions"** mapping table in `roadmap.md` (one row per release version →
milestone/wave + epic(s) delivered), verified by the create-prd verifier's
0-orphan-milestone coverage sub-check (ADR 0053).

The `standards` chain level has a documentary counterpart in this repo at
`docs/standards/standards.md` (e.g. the test-file-naming standard); with
`standards_path` unset, these standards are enforced by guard tests and pipeline
guidance rather than as a runtime-verified conformance level.

---

## tabp plugin contracts

Source: `MAR-2/specs/01-tabp-state-json-schemas.md`. Schemas live in
`plugins/tabp/schemas/`. Validated at runtime by `tabp_helper.py` (spec 02).
All `$id` URIs use tabp-namespaced GitHub paths; no acs identifiers.

### tabp settings.json

**File path:** `<project>/tabp settings.json` — literal filename with a space,
at the Cowork project folder root (NOT inside `.tabp/`). Read by
`tabp_helper.py settings-read --project-dir <path>` at skill start. Validated
by `tabp_helper.py settings-validate --project-dir <path>` before reading.

**Schema:** `plugins/tabp/schemas/settings.schema.json` (JSON Schema
Draft-2020-12; all fields optional; `additionalProperties: false`;
`state_write_mode` enum `["helper", "instructed"]`; no `workspace_path`, no
secrets).

**Shape table:**

| Field | Type | Default | Notes |
|---|---|---|---|
| `screening_model` | string | coordinator default Sonnet | Model for per-CV screening subagents. |
| `synthesis_model` | string | coordinator default Opus | Model for synthesis subagent. |
| `cv_folder` | string | `./cvs` | Relative to project folder. |
| `jd_folder` | string | `./jds` | Relative to project folder. |
| `state_write_mode` | `"helper"` or `"instructed"` | `"helper"` | `"instructed"` when Cowork denies shell (degraded mode). |

**Observable fallback envelope** — `settings-read` stdout:

```json
{
  "settings": { ...resolved fields... },
  "settings_source": "file" | "absent" | "corrupt",
  "from_file": [...keys present in file...],
  "from_default": [...remaining keys that fell back to defaults...]
}
```

When the file is absent: `settings_source = "absent"`, `from_file = []`, all
five keys in `from_default`. When the file is corrupt: `settings_source =
"corrupt"`, same. The coordinator reads resolved values from
`result["settings"]` and can surface which settings came from the file vs.
which are defaults.

**MAR-38 — `model_pricing` (runtime-read-only, no schema file):** an optional
`model_pricing` block may appear in `settings.json` to override the built-in
pricing snapshot on a per-model basis. No `settings.schema.json` is created for
this key (DEV-1: MAR-3-owned schema boundary; would activate `ci.yml:197-199`).
Format:
```json
{
  "model_pricing": {
    "claude-opus-4-8":   { "input_per_mtok": 15.00, "output_per_mtok": 75.00 },
    "claude-sonnet-4-6": { "input_per_mtok":  3.00, "output_per_mtok": 15.00 }
  }
}
```
Values are USD per million tokens (numbers). No credentials or API keys.
If absent, the built-in `_MODEL_PRICING` snapshot (dated `_PRICING_SNAPSHOT_DATE`)
is used. Surfaced via `settings-read` output when present (`_cmd_settings_read`,
MAR-38). Validated/sanitised at usage-read time by `_resolve_pricing`.

### `.tabp/` state record schemas

All state files are written to `<project>/.tabp/` in the Cowork project folder.
PII-minimal rule: `candidate_name` holds only a name or anonymised label — no
contact details, no protected-class attributes, no secrets.

#### Run record — `run.json`

Path: `<project>/.tabp/runs/<run-id>/run.json`
Schema: `plugins/tabp/schemas/run.schema.json`

| Field | Type | Description |
|---|---|---|
| `run_id` | string | Unique run ID, format `run-<ISO8601>`. E.g. `run-20260620T091530Z`. |
| `skill` | string | Skill name. Always `"screen-cvs"` for the current skill. |
| `started_at` | date-time | ISO-8601 datetime the run started. |
| `ended_at` | date-time or null | ISO-8601 datetime the run ended. Null while `in_progress`. |
| `status` | enum | `"in_progress"`, `"completed"`, `"failed"`, `"interrupted"`. |
| `stop_reason` | string or null | Reason run stopped early. Null unless `failed` or `interrupted`. |
| `state_write_mode` | enum | `"helper"` (tabp_helper.py subcommands) or `"instructed"` (degraded mode). |
| `usage.usage_source` | enum | `"cowork"` (self-reported, cost_basis=actual), `"claude-code"` (transcript tokens, cost_basis=estimate), `"estimate"` (heuristic, cost_basis=estimate), `"unavailable"` (no data). |
| `usage.tokens_in` | integer or null | Input token count. Null when `usage_source = "unavailable"`. |
| `usage.tokens_out` | integer or null | Output token count. Null when `usage_source = "unavailable"`. |
| `usage.cost_usd` | number or null | Cost in USD. Null when `usage_source = "unavailable"`. |
| `usage.cost_basis` | enum (optional) | `"actual"` (self-reported by runtime), `"estimate"` (derived from tokens x pricing), `"unavailable"` (no cost data). Absent on legacy records — treated as `"unavailable"`. |
| `usage.duration_seconds` | number or null | Wall-clock duration in seconds. |
| `candidates_screened` | integer | Number of candidates screened. |
| `jd_slug` | string | Job description slug. E.g. `"backend-engineer"`. |
| `scorecard_file` | string (optional) | Filename of the Excel scorecard produced. |

#### Evidence record — `evidence-<candidate-id>.json`

Path: `<project>/.tabp/runs/<run-id>/evidence-<candidate-id>.json`
Schema: `plugins/tabp/schemas/evidence.schema.json`

| Field | Type | Description |
|---|---|---|
| `run_id` | string | Parent run identifier. |
| `candidate_id` | string | Unique candidate ID within the run. |
| `candidate_name` | string | Name or anonymised label only (PII-minimal rule). |
| `requirements` | array | Per-requirement judgments. Each item: `requirement`, `category`, `judgment`, `evidence` (minLength:1 — AC-4). |
| `score` | number | Composite score 0..100. |
| `band` | enum | `"Strong"`, `"Moderate"`, `"Weak"`. |
| `recommendation` | enum | `"Recommend"`, `"Hold"`, `"Reject"`. |
| `must_have_gate` | string | Pattern `^(OK\|Missing:.+)$`. `"OK"` or `"Missing:<list>"`. |
| `fairness_check_passed` | boolean | Whether the fairness guardrail check passed. |
| `bias_flags` | array (optional) | List of bias flag strings. Empty when none detected. |

AC-4 constraint: every `requirements[].evidence` must be a non-empty string (minLength:1).
No invented evidence is permitted; all judgments must cite CV source.

#### Decision record — `decision.json`

Path: `<project>/.tabp/runs/<run-id>/decision.json`
Schema: `plugins/tabp/schemas/decision.schema.json`

| Field | Type | Description |
|---|---|---|
| `run_id` | string | Parent run identifier. |
| `verification_passed` | boolean | Whether the self-verification step passed (AC-3). |
| `verification_notes` | string (optional) | Notes from the self-verification step. |
| `presented_at` | date-time | ISO-8601 datetime when results were presented. |
| `sign_off` | object or null | Null until recruiter confirms in-chat. Object has: `recruiter` (string), `confirmed_at` (date-time), `notes` (string, optional). |

#### Append-only run history — `history.json`

Path: `<project>/.tabp/history.json`
Schema: `plugins/tabp/schemas/history.schema.json`

| Field | Type | Description |
|---|---|---|
| `runs` | array | Append-only array of run summary objects. `runs[-1]` is the most recent run. |
| `runs[].run_id` | string | Run identifier. |
| `runs[].skill` | string | Skill name. |
| `runs[].started_at` | date-time | Run start time. |
| `runs[].status` | enum | `"in_progress"`, `"completed"`, `"failed"`, `"interrupted"`. |
| `runs[].ended_at` | date-time or null (optional) | Run end time. |
| `runs[].candidates_screened` | integer (optional) | Number of candidates screened. |
| `runs[].jd_slug` | string (optional) | Job description slug. |
| `runs[].duration_seconds` | number or null (optional) | Wall-clock duration. |
| `runs[].usage_source` | enum (optional) | `"cowork"`, `"claude-code"`, `"estimate"`, or `"unavailable"`. |

The append-only invariant (no deletion) is enforced at runtime by `tabp_helper.py`.

#### Lock — `.lock`

Path: `<project>/.tabp/.lock`
Schema: `plugins/tabp/schemas/lock.schema.json`

| Field | Type | Description |
|---|---|---|
| `pid` | integer (>= 1) | PID of the process holding the lock. |
| `hostname` | string | Hostname of the machine holding the lock. |
| `created_at` | date-time | ISO-8601 datetime the lock was acquired. |

Stale locks (process gone or different host) are reported for manual removal,
never auto-stolen. Released when the run transitions out of `in_progress`.

### `/tabp:usage` read contract output shape

_Implemented in MAR-38. Replaces the MAR-6 placeholder stub._

`tabp_helper.py usage-read --project-dir <path> [--run-id <id>|all]` aggregates
from `history.json` + per-run `run.json` records and prints to stdout:

```json
{
  "total_runs": 12,
  "completed_runs": 11,
  "failed_runs": 1,
  "total_candidates_screened": 47,
  "total_duration_seconds": 19205,
  "total_tokens_in": 284000,
  "total_tokens_out": 52000,
  "total_cost_usd": 4.12,
  "cost_basis": "estimate",
  "pricing_snapshot_date": "2025-08-01",
  "usage_note": "Cost is a derived estimate (tokens x pricing table snapshot 2025-08-01). Token counts are actuals from Claude Code transcript where available; estimate otherwise. Unavailable runs excluded from totals.",
  "runs": [
    {
      "run_id": "run-20260620T091530Z",
      "started_at": "2026-06-20T09:15:30Z",
      "status": "completed",
      "candidates_screened": 5,
      "duration_seconds": 1902,
      "usage_source": "claude-code",
      "tokens_in": 28000,
      "tokens_out": 5200,
      "cost_usd": 0.41,
      "cost_basis": "estimate",
      "usage_note": "Tokens: actuals from Claude Code transcript. Cost: derived estimate."
    }
  ]
}
```

When `usage_source = "unavailable"`: `tokens_in`, `tokens_out`, `cost_usd` are
`null`; `cost_basis` is `"unavailable"`; the run is included in `runs[]` but
excluded from token/cost totals.

When `usage_source = "cowork"`: `cost_basis = "actual"` (self-reported by
Cowork runtime — forward hook, MAR-40).

`pricing_snapshot_date` is always present (`_PRICING_SNAPSHOT_DATE` constant).
`cost_basis` is the aggregate: `"actual"` if any non-unavailable run has actual,
else `"estimate"`, else `"unavailable"`.

Read-only: no writes, no network calls, no re-screening. No transcript text is
persisted into `.tabp/` state files.
