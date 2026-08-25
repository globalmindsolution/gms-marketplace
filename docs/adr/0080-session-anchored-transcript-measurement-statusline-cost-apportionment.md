# 0080 — Session-anchored transcript measurement with statusLine-sourced real-cost apportionment, superseding an acs-owned price table

**Status**: Accepted · **Date**: 2026-08-25

## Context

`acs`'s cost/time tracking had two independent defects, both instances of the
same bug: "unknown" was rendered as "zero."

1. **Time.** `run_seconds(entry)` (`plugins/acs/hooks/scripts/acs_lib.py`)
   returned `0` for a run with no `ended_at` (in-progress) or an invalid
   interval, and `compute_ticket_totals` summed that `0` into
   `totals.working_seconds` while still incrementing `totals.runs` — so an
   in-progress run dragged every average down. `metrics_aggregate.py`'s own
   `_elapsed_seconds` already returned `None` for the identical guard: two
   helpers, one guard, opposite fallbacks.
2. **Cost/tokens.** Pipeline cost/tokens were self-estimated in two
   independent places: a subagent-authored `<metrics tokens-input=".."
   tokens-output=".." cost-usd="..">` element on `<result>` messages
   (all attributes optional, `default="0"`), scraped into panel 6 ("token
   burn by role"); and a coordinator-authored top-level `tokens`/`cost_usd`
   pair in the skill's own result document, which the SKILL.md charters
   instructed subagents to fill with their own self-estimate. Measured against the
   live transcript for one real session, the self-estimate was not merely
   low, it was uncorrelated with reality (roughly 500x under on input
   tokens, 9x under on output, while raw non-cache input was itself ~90x
   *over* that one component) — the estimates carry no reliable signal at
   any scale.

## ADR 0026 as precedent, and the delta from it

`docs/adr/0026-tabp-hybrid-cost-sourcing.md` established the sibling `tabp`
plugin's cost model: **D3a** read real `message.usage` token counts from the
Claude Code transcript tree correlated by a `<cwd-slug>` directory scan, and
**D3b** derived a dollar figure by multiplying those tokens against an
acs-owned, settings-overridable price table (`_MODEL_PRICING`), always
labeled `cost_basis="estimate"` (never `"actual"`) because the *cost* itself
was derived, not self-reported. This design inherits ADR 0026's governing
invariants wholesale — never label a derived cost `"actual"`, never
zero-pad an unavailable run, always keep unavailable runs in `runs[]` for
auditability — but supersedes its two load-bearing mechanics:

- **Correlation.** Porting `tabp_helper.py`'s `_cwd_slug`-based transcript
  scan verbatim against the real runtime surfaced four defects (verified by
  running the tabp helpers in this repo against a live transcript tree):
  - **P1 — leading-dash slug mismatch.** `_cwd_slug` strips the leading `-`
    from the directory name; Claude Code's real project directory keeps it
    (`-home-user-gms-marketplace`, not `home-user-gms-marketplace`). A
    verbatim port silently read `(0, 0, None)` — zero tokens, no error.
  - **P2 — cache tokens ignored.** tabp's reader summed only
    `input_tokens`/`output_tokens`; real `message.usage` also carries
    `cache_creation_input_tokens`/`cache_read_input_tokens`, which dominate
    real usage by orders of magnitude.
  - **P3 — subagent transcripts live in a subtree tabp never globs.** tabp's
    reader glob is non-recursive (`<slug>/*.jsonl`); the real layout nests
    subagent transcripts under `<slug>/<sessionId>/subagents/agent-*.jsonl`,
    so subagent work was silently absent from every tabp-derived figure.
  - **P4 — model pricing keys don't match.** tabp's `_MODEL_PRICING` keys
    (`claude-opus-4-8`/`claude-sonnet-4-6`) don't match the model names this
    repo's own `.acs/settings.json` and live transcripts actually use
    (`claude-sonnet-5`/`claude-opus-5`).

  This design fixes P1 and P3 **structurally**, not by patching the
  symptom: `usage_reader.py` never constructs a slug at all — it reads the
  *exact* `transcript_path` recorded on the run entry, captured from the
  genuine Claude Code `PreToolUse(Skill)` hook envelope by a new
  session-correlation marker (`acs_lib.record_session_marker`, written by
  `pre-<skill>.py`/`acs_lib.run_pre` and read by `skill-start.py`), plus a
  *recursive* walk of that session's own `subagents/` subtree. This is a
  precision improvement over ADR 0026's cwd-slug + time-window approach:
  correlation is by the runtime's own `session_id`/`transcript_path`, never
  a directory-name guess, so two tickets worked in overlapping windows in
  the same project directory cannot cross-contaminate each other's figures.
  `usage_reader.py` fixes P2 by reading all four `message.usage` integer
  fields unconditionally.
- **Pricing.** P4 is moot under this design, not patched: acs does not own a
  price table at all. Where ADR 0026 derives cost from tokens x an
  acs-maintained price snapshot, this design sources cost from Claude Code's
  own real-time cost computation, sampled off the opt-in `statusLine` hook's
  stdin payload (`cost_sampler.py`) and apportioned across roles by measured
  token share (`cost_sampler.allocate_cost`) via a cursor-based,
  non-overlapping consumption rule that makes double-charging structurally
  impossible. No `model_pricing` settings key, no dated snapshot to go
  stale, no second acs-computed dollar figure that can silently diverge
  from what Claude Code itself believes the session cost to be.

## Mechanism rejected on topology, not preference: D8-B

One real alternative was evaluated and rejected for a structural reason, not
a stylistic one: reading `total_cost_usd` off the `claude -p --output-format
json` process-exit envelope, the mechanism `evals/acs/harness.py` already
uses for headless eval runs (`out["cost_usd"] = env.get("total_cost_usd")`).
That envelope is real, grep-confirmed, and needs no opt-in — but it exists
only in a **headless, one-process-per-prompt** topology. The live `/acs:*`
pipeline is the opposite shape: one long-running interactive session in
which the coordinator and its Task-tool subagents run without any process
exit between skills, so there is no envelope to read at a skill boundary.
This mechanism is valid for the eval harness and unavailable to per-skill
attribution in a live session — disqualified by topology, not by
preference. The chosen mechanism (statusLine stdin sampling) is the only
surface in the live-session topology that carries a Claude-computed dollar
figure at all.

## Decision

1. **Elapsed time.** A single `None`-safe primitive,
   `acs_lib.elapsed_seconds(start, end)`, is the one source of truth for
   wall-clock duration; `acs_lib.run_seconds(entry)` and
   `metrics_aggregate._elapsed_seconds(a, b)` both become one-line adapters
   over it. A missing/malformed/inverted interval is `None` — excluded from
   `working_seconds` sums — while still counting the run itself via additive
   `runs_timed`/`runs_untimed` counters, never rendered as a phantom `0`.
2. **Correlation.** `pre-<skill>.py`/`acs_lib.run_pre` captures
   `session_id`/`transcript_path` off the genuine `PreToolUse(Skill)` hook
   envelope into a ticket-independent session marker
   (`sessions/<checkout_id>-session.json`), wrapped in its own
   `try/except Exception: pass` so a marker-write bug can never turn into a
   blocked gate (`run_pre`'s outer handler fails closed). `skill-start.py`
   reads that marker (rejecting a foreign `checkout_id` or one older than 15
   minutes) and threads `session_id`/`transcript_path`/`checkout_id` onto the
   new run entry. A rejected or absent marker never falls back to slug
   construction — that would silently reintroduce P1.
3. **Token measurement.** At finalize time, `usage_reader.py` reads the
   run's exact recorded `transcript_path` plus its `subagents/` subtree,
   counting all four `message.usage` integer fields and bucketing them by
   role (`coordinator` for main-session attributed work, `planner`/
   `executor`/`verifier`/`other` for subagent `attributionAgent` values, an
   `unattributed` bucket — never redistributed onto attributed roles — for
   same-window tokens with no attribution). It never raises: any I/O
   failure, missing marker, empty window, or cap breach (32 MiB / 64 files)
   degrades to `degraded=true` with a reason, and a run that resolves zero
   real tokens is treated as degraded, never a misleadingly valid `0`.
4. **Cost.** `cost_sampler.py` samples a shape-agnostic `total_cost_usd`
   figure off the `statusLine` hook's stdin payload on every invocation
   (`record_cost_sample`, called from `statusline.py`'s `main()`, before
   render, its own `try/except Exception: pass`), and at a run's finalize
   consumes the unconsumed portion of that per-checkout sample log since a
   persisted allocation cursor (`allocate_cost`) — the "before" edge is
   always the cursor, so a sample already consumed by one run can never
   again serve as another run's charge. The consumed delta is apportioned
   across the run's roles by measured token share. Every figure carries a
   `cost_basis`: `measured` (the run-level `cost_usd` — the attributed-token
   share of the real session-window delta `statusLine` reported, i.e. that
   delta net of the excluded/unattributed token share per C-8's "drop, don't
   redistribute" policy — still sourced directly from Claude Code's own real
   number, never an acs-invented estimate), `apportioned` (the further
   per-role split of that same attributed share — a stated approximation,
   since acs owns no per-model price), or `unavailable` (never fabricated,
   never zero-padded).
5. **Self-estimate removal.** The `<metrics>` XML element is removed
   outright from `acs-messages.xsd` and from every one of the 45 agent
   charter files that emitted it; the retired self-estimate instruction for
   `tokens`/`cost_usd` is removed from `code/SKILL.md` and
   `merge-pr/SKILL.md`. `validate_xml.py`'s `CHILD_ORDER["result"]` and
   `ALLOWED_ATTRS` — the actual in-process enforcement path, not the XSD
   alone — reject a stray `<metrics>` element post-change. One source of
   truth; no mislabeling risk possible.
6. **Historical data.** Forward-only: historical tickets keep their prior
   self-estimated figures; no backfill. A pre-cutover run with no
   `cost_basis` field is treated identically to `cost_basis="unavailable"`
   by `compute_ticket_totals`/`update_metrics` — excluded from cost sums,
   counted in `runs_cost_unavailable`.

## Supersession

This ADR **supersedes `docs/adr/0013-metrics-derives-panels-from-artifacts.md`
and `docs/adr/0016-metrics-bounded-single-pass-walk.md`** on the single point
where both describe deriving panel 6 ("token burn by role") from the
`<metrics>` XML element scraped out of phase artifact files. Panel 6 is now
sourced from each run entry's measured `role_usage` field
(`metrics_aggregate._accumulate_burn`), not from artifact XML at all on this
one point; both ADRs otherwise remain accurate and are **not edited** — ADRs
are immutable historical records, and superseding here is recorded
explicitly rather than left as silent contradiction. `0013`/`0016` continue
to contain the literal string `<metrics` by design.

## Consequences

- Every persisted and rendered cost/time figure carries an honest basis
  label (`measured`/`apportioned`/`unavailable` for cost; a run counted in
  `runs_timed` or `runs_untimed` for time); nothing is silently zero-padded.
- Coverage is contingent on `statusLine` opt-in
  (`/acs:initialize` Step 7b) and on an unconsumed sample existing in a
  run's window. A repo that never opts in still gets accurate `measured`
  token counts and an honest `unavailable` cost — a strict improvement over
  the prior uncorrelated self-estimate, never a regression.
- `cost_basis="measured"` is precisely delta-since-last-charge, not
  delta-during-this-run's-own-window: the allocation cursor may sit before
  the run's own `started_at`, so a charged delta can include spend from
  before the run began (idle chat, a previous unrelated run). This is a
  disclosed limitation of the cursor mechanism, not a bug, and does not
  change the direction of the invariant — the cursor rule bounds the sum of
  all charged deltas to at most the total spend observed, so sparse
  sampling produces *missing* runs, never *duplicated* ones.
- `<metrics>` is retired from the subagent-to-coordinator message contract
  permanently; a coordinator that still populates a result document's
  top-level `tokens`/`cost_usd` fields has them silently ignored by
  `finalize_run`, not rejected — a soft landing for anything not yet
  migrated.
- `usage_reader.py`'s privacy boundary is structural, not a policy note: it
  opens only `*.jsonl` files (never a `*.meta.json` sidecar — the suffix
  filter excludes it by construction) and reads only the four integer usage
  fields, `message.model`, `timestamp`, and the attribution fields — never
  `message.content`, prompt text, or tool results.
- **Runtime layout coupling (residual risk, tracked for future diagnosis).**
  `<transcript_dir>/<session_id>/subagents/agent-*.jsonl` plus an in-record
  `attributionAgent` field is an internal Claude Code layout with no
  compatibility guarantee. Observed this session:
  `message.usage` carries `input_tokens`/`output_tokens`/
  `cache_creation_input_tokens`/`cache_read_input_tokens`; subagent
  transcript records carry `attributionAgent` values matching the
  `acs:<skill>-<role>` charter-file naming convention (e.g.
  `acs:create-design-planner`, suffix-matched to `planner`/`executor`/
  `verifier`) plus non-triad values (e.g. `Explore`, bucketed `"other"`
  rather than dropped); every record carries a `message.version` field. If
  a future Claude Code release changes this layout, `usage_reader.py`
  degrades loudly (`degraded=true` with a reason) rather than silently
  reporting zero — the same failure mode ADR 0026's cwd-slug defect proved
  was otherwise invisible.
