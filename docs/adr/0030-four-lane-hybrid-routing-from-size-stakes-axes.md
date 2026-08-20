# 0030 — Adopt four-lane hybrid routing (TRIVIAL/SMALL/STANDARD/COMPLEX) from size x stakes axes

**Status**: Accepted · **Date**: 2026-06-25

## Context

Today every ticket runs the same full pipeline regardless of complexity:
create-ticket → create-design (when needed) → create-spec → code → create-pr → merge-pr.
A trivial typo fix goes through the same verification depth as a security-sensitive payment
integration. This imposes unnecessary overhead on low-risk work while providing no
extra safety for high-stakes changes.

The decision space was: (a) how many lanes, (b) what axes drive routing, (c) whether
the routing function is deterministic or probabilistic, and (d) what the default is
when inputs are absent.

## Decision

**Adopt a four-lane model driven by two authoritative axes (`size` × `stakes`):**

| Lane | Size | Stakes | Verify depth |
|------|------|--------|--------------|
| TRIVIAL | trivial | not high | fast-lane (create-spec folded into /code plan phase) |
| SMALL | small | not high | fast-lane |
| STANDARD | standard or any with stakes=high or needs_design=True | — | full verify |
| COMPLEX | large or epic | — | full verify |

**Routing function `derive_lane(size, stakes, needs_design, ticket_type)` is deterministic
(pure function, fixed rule order):**

1. `ticket_type == "epic"` → COMPLEX (always full rigor for epics)
2. `size == "large"` → COMPLEX
3. `stakes == "high"` → STANDARD floor (never below full verify for high-stakes work)
4. `needs_design == True` → STANDARD floor
5. `size == "standard"` → STANDARD; `size == "small"` → SMALL; `size == "trivial"` → TRIVIAL
6. Default → STANDARD (conservative: absent/unknown inputs never silently produce a fast lane)

**Conservative default:** absent or unrecognized inputs always resolve to STANDARD — the same
full-rigor behavior as today. No existing ticket's effective verification changes because the
absent-axis path yields STANDARD, identical to the current un-classified behavior.

## Alternatives considered

- **Two-lane (fast/full):** insufficient granularity; TRIVIAL and SMALL need different gate
  behavior (SMALL still has some spec work; TRIVIAL skips it entirely).
- **Probabilistic routing (ML-scored):** non-deterministic; untestable without a model in CI;
  inconsistent with the "deterministic layer" invariant.
- **LOC-only routing:** LOC is a proxy, not a dimension; a 10-line change in `auth/` deserves
  more rigor than a 200-line change in documentation.
- **User-only routing (no recommendation):** puts all cognitive load on the engineer; the
  path-glob recommendation (Spec 02) reduces the burden while keeping the user in control.

## Consequences

- Every ticket gets a `lane` field (TRIVIAL/SMALL/STANDARD/COMPLEX) at mint time.
- The routing function is the single canonical authority; no caller re-implements the logic.
- STANDARD and COMPLEX lanes are unchanged from today — no regression for the common case.
- TRIVIAL and SMALL lanes (gate changes in MAR-59/Child 4) reduce pipeline overhead for
  low-risk work.
- The `lane` field is a derived cache; the axes (`size`, `stakes`) are authoritative.
  The cache can always be recomputed: `derive_lane(size, stakes, needs_design, type)`.
- Metrics layer gains lane-sliceable data (G14/G15) via the pipeline-state and index writes
  (D7, MAR-56/spec 01).

## Amendment — MAR-156

**Date**: 2026-07-29 · **Status**: Accepted (stale-reference note)

`/acs:create-spec` is deleted outright (ADR 0066): the pipeline order in
Context above is now `create-ticket → create-design (when needed) → code →
create-pr → merge-pr`, with no standalone create-spec step. The Decision
table's TRIVIAL row ("create-spec folded into /code plan phase") is
superseded by ADR 0066's every-lane fold: folding no longer distinguishes
TRIVIAL from SMALL/STANDARD/COMPLEX, since it now applies on every lane
identically. The four-lane routing decision itself (`derive_lane`, the
size/stakes axes, the routing table and rule order above) is UNCHANGED and
unamended beyond this note — this ticket does not touch lane derivation.

## Amendment — MAR-76

**Date**: 2026-08-20 · **Status**: Accepted (rule removal)

This amendment supersedes the MAR-156 amendment's closing sentence above:
the four-lane routing decision is no longer unamended, because `needs_design`
narrows to epic-only in this changeset (`plugins/acs/skills/create-ticket/SKILL.md`)
and Rule 1 already routes every epic to COMPLEX before Rule 4 could ever be
reached — so Rule 4 was unreachable for epics and unwanted for non-epics, and
`derive_lane` drops it:

- Rule 4 ("`needs_design == True` → STANDARD floor", Decision above) is
  **removed**. The Decision table's STANDARD row ("standard or any with
  stakes=high or needs_design=True") now reads, in the code, "standard, or
  any with stakes=high" (`plugins/acs/hooks/scripts/acs_lib.py:84-108`).
- The rule list renumbers 1-6 → 1-5 (`acs_lib.py:87-93`): Rule 3 (high-stakes
  floor) is followed directly by the size dispatch, then the default.
- Rule 1 (`ticket_type == "epic"` → COMPLEX) and Rule 3 (`stakes == "high"` →
  STANDARD floor, non-bypassable per the surviving decision above) are
  **untouched** by this amendment.
- `derive_lane`'s signature (`size, stakes, needs_design, ticket_type`) is
  unchanged for call-site stability; the `needs_design` argument is still
  accepted but no longer affects the result.
