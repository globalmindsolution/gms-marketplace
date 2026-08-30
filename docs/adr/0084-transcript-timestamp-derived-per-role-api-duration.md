# 0084 — Transcript-timestamp-derived per-role API duration for `/acs:usage`, capped at `MAX_RECORD_GAP_SECONDS = 60`

**Status**: Accepted · **Date**: 2026-08-30

## Context

MAR-5 (Seam B of epic MAR-2) adds a per-role **API-duration** figure to
`/acs:usage`, mirroring Claude Code's own `/usage` "Total duration (API)"
vs. "Total duration (wall)" split. Two candidate measurement mechanisms
were open (design.md's D4):

- **Option A** — a statusLine-sampled `cost.total_api_duration_ms` field,
  apportioned across roles by token share, following the same
  cursor-based no-double-charge pattern `cost_sampler.py` already uses for
  `cost.total_cost_usd` (ADR 0082).
- **Option B** — a transcript-timestamp-derived per-record latency,
  computed inside `usage_reader`'s existing single transcript pass, with
  no new module and no new state file.

The user selected **Option B**, with an explicit requirement: the figure
must be **labeled a derived approximation** (it mixes local tool/idle time
with real API wait) in both the documentation and the UI, and the chosen
gap-cap constant must be justified from real, empirically measured data,
not picked arbitrarily.

**No per-call latency field exists anywhere in the transcript.** The only
usable signal is each record's own `timestamp`, already read by
`usage_reader` at every in-window record (`usage_reader.py:203`) and
already named in the module's privacy-boundary statement — deriving
duration from it widens no boundary.

**Finding M1 — `message.usage` appears on assistant records only.**
Enumerated across the sample used for this ADR (13 files: one main-session
transcript plus its 12-file `subagents/` subtree):

```
('assistant', has message.usage=True)   966
('user',      has message.usage=False)  588
('<no message>',              False)    493
```

Not one `user`-role or message-less record carries a `message.usage`
block. This is the finding the whole design turns on: a gap can only be
*attributed* to a token-bearing (assistant) record, since that is the only
place a role/token bucket already exists to charge it to.

## Decision

**Attribution rule.** Charge each token-bearing (assistant) record the gap
since its immediate predecessor record in the same file:

1. `prev_ts` is a **per-file** local, seeded `None` at the start of each
   file (main session and every subagent file track predecessors
   independently — no cross-file bleed, no subagent double-count into the
   coordinator's figure, since a subagent's own wall time elapses before
   the main session's Task tool-result record, which by **M1** carries no
   `usage` and is therefore never charged).
2. `prev_ts` advances for **every** in-window timestamped record,
   including ones that carry no `usage` block. This is what makes the gap
   preceding a non-token-bearing record (the tool-execution leg: assistant
   invokes a tool → tool result) structurally vanish rather than being
   re-attributed to the next assistant record — only the *response* leg
   (predecessor → assistant record) is ever charged.
3. A gap is attributed **only** when it precedes a token-bearing record;
   the gap before a non-token-bearing record is dropped, never carried
   forward.
4. **Out-of-window records neither contribute nor advance `prev_ts`** — a
   gap straddling the run window's boundary is never charged.
5. A **non-monotonic** gap (the predecessor timestamp is not strictly
   before the current one — transcript records are not guaranteed to be
   written in timestamp order) contributes **zero**, never a negative
   duration.
6. Any attributed gap is **capped** at `MAX_RECORD_GAP_SECONDS = 60`
   seconds.

**Naive fold is badly contaminated (measured, not assumed).** Before
adopting the rule above, the naive alternative — fold every consecutive
gap in the file, uncorrected — was measured on the same 13-file sample:

```
gaps=1838  raw_sum=17829.0s  negative=35 (min -573.4s)
  cap= 30s ->  5995.3s (33.6% of raw)   cap= 60s ->  8099.4s (45.4%)
  cap=120s -> 11463.4s (64.3%)          cap=300s -> 16109.0s (90.4%)
positive gaps: median=1.2s p75=2.7s p90=9.3s p95=24.4s p99=309.5s max=3793.0s
```

A **2.69×** spread across plausible cap choices (5995.3 → 16109.0), a
63-minute maximum gap that is obviously human idle time, and 35
non-monotonic (negative) gaps — under this fold the cap constant would be
the dominant term in the rendered number, making it indefensible as a
disclosed approximation.

**The attribution rule above removes most of that contamination *before*
any cap is applied.** Measured on the identical sample:

```
token-bearing records: 964   non-token records (predecessor advanced, gap dropped): 913
attributed gaps: 964  raw_sum=6462.0s  negative=1 (min -0.7s)
positive: median=2.0s p75=4.0s p90=11.4s p95=19.8s p99=106.0s max=295.8s
  cap= 30s -> 4243.9s (65.7% of raw)  clipped=30 gaps (3.1%)  discarded=2218.7s
  cap= 60s -> 4971.9s (76.9% of raw)  clipped=19 gaps (2.0%)  discarded=1490.7s
  cap=120s -> 5757.6s (89.1% of raw)  clipped=10 gaps (1.0%)  discarded= 705.0s
  cap=300s -> 6462.6s (100.0% of raw) clipped= 0 gaps (0.0%)  discarded=   0.0s
```

**Cap decision: `MAX_RECORD_GAP_SECONDS = 60`**, justified against this
distribution:

1. **It clears the body of genuine turn latencies with ~3x headroom.**
   p95 = 19.8 s, p90 = 11.4 s — 60 s does not truncate normal generation.
2. **It still functions as a real guard**, because it sits below p99
   (106.0 s). 120 s and 300 s sit **at or above** p99 and clip only
   1.0% / 0.0% of gaps respectively — 300 s clips literally nothing on
   this sample, making it a decorative ceiling with no protection against
   a pathological gap (an interrupted turn, a user stepping away between
   a tool result and the next response).
3. **30 s is too tight.** At only ~1.5x p95 it discards 2218.7 s — **34%
   of the attributed total** — biasing the figure low by truncating
   legitimate long-generation turns, an error the cap constant itself does
   not disclose to the reader.
4. **60 s is legible.** "No single turn is credited more than one minute
   of API time" is a sentence a dashboard reader can hold; an
   unexplainable constant undermines the honesty labeling this decision
   requires.
5. **Its residual sensitivity is small and disclosable.** Moving the cap
   across the entire 30-300 s range moves the derived total by **1.52x**
   (4243.9 → 6462.6) — versus **2.69x** under the naive fold — and this
   sensitivity is stated below as a central consequence, not buried.

`role_duration` is published as a new array on the run entry, parallel to
and independent of `role_usage` (whose shape is completely unchanged):
`[{role, api_duration_ms, duration_basis}, ...]`. A role that accumulates
`0` (every one of its records was a file's first in-window record, so no
gap was attributable) publishes `api_duration_ms: null`,
`duration_basis: "unavailable"` — **never `0`**, since `0` would misread
as "measured zero API time" rather than "nothing was attributable."
`duration_basis` is **always** `"derived"` (numeric case) or
`"unavailable"` (no attribution) — **never `"measured"`** — because this
figure is not, and can never become, a per-call measurement under Option
B. `metrics_aggregate` folds `role_duration` into panel 6's repo-scope
buckets by role, in the same walk that already sums `role_usage`/
`model_usage` (zero extra file reads); `usage_by_ticket` and panel 3 carry
no duration keys — this figure is repo-scope only. `metrics_render` shows
it as one appended `api duration` column on both the terminal and HTML
`/acs:usage` surfaces, prefixed `~` when derived and rendering the
existing `UNAVAILABLE` literal when no duration was derived, plus a fixed
caption below the panel-6 table on both surfaces stating the derivation
and the 60 s cap in one sentence — satisfying the "explicit in docs and
UI" requirement.

## Consequences

- **The figure is an upper bound on real API wait, never a measurement.**
  The attributed interval still contains any local latency between the
  predecessor record being written and the API response beginning; it can
  never be reconciled to a true per-call latency without a real API-side
  timestamp, which the transcript does not carry.
- **The attribution rule, not the cap, is the primary filter.** The raw
  attributed total already falls from 17829.0 s to 6462.0 s (−64%) with
  **no cap at all** — the rule alone removes most of the contamination the
  naive fold suffered from.
- **The cap's residual sensitivity is disclosed, not hidden: 1.52x across
  the full 30-300 s range** (4243.9 s → 6462.6 s), down from 2.69x under a
  naive all-gap fold. A reader who distrusts the constant can bound how
  far a different choice would move the number from this ADR alone.
- **Subagent wall time never double-counts into the coordinator's
  figure.** It elapses before the main session's Task tool-result record,
  which by M1 carries no `usage` and is therefore never charged — a
  property of the attribution rule, not an added guard.
- **49% of timestamped records contribute nothing.** 913 of 1877
  timestamped records in the sample are non-token-bearing; the figure
  measures response legs only, by design, never tool-execution or idle
  legs charged to the wrong record.
- **Non-monotonicity is a residual, not a load-bearing concern.** The
  attribution rule alone reduces negative gaps from 35 (min −573.4 s,
  naive fold) to 1 (min −0.7 s) on the same sample; the zero-on-negative
  guard remains mandatory (a single clock artifact must never subtract)
  but is no longer doing the bulk of the contamination-removal work.
- **The measurement is one repo's transcript store.** The cap justification
  rests on 13 files / 1877 timestamped records / 964 token-bearing
  records from this container. `MAX_RECORD_GAP_SECONDS` is a single named
  module constant — a revisable, single-line choice — and this ADR's own
  1.52x sensitivity figure bounds how far a different sample could move
  the answer.
- **ADR 0082 is extended, never edited.** This ADR adds a new derived
  signal (`role_duration`) alongside ADR 0082's measured `role_usage`/
  `model_usage`/cost pipeline; ADR 0082 itself carries no diff.
- **Zero migration.** `role_duration` is additive on the run entry
  (`skill-state.schema.json`, not added to `required`); a run entry
  finalized before this shipped simply lacks it and renders `unavailable`
  on the new column — forward-only, no backfill, the same pattern
  `role_usage`'s original MAR-1 rollout and `model_usage`'s MAR-3 rollout
  both used.
