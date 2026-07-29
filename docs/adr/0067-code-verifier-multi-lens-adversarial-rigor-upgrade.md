# 0067 — code-verifier multi-lens adversarial rigor upgrade (`verify_depth=="full"` only)

**Status**: Accepted · **Date**: 2026-07-29

## Context

Epic MAR-155's design D4 ("code-verifier rigor upgrade shape") decided that
`verify_depth=="full"` tickets (STANDARD/COMPLEX, or any high-stakes ticket)
should move from a single verifier pass toward Anthropic's official
`/code-review` shape: multiple independent parallel lenses examining the
same diff from different evidence sources, then a separate confidence-
scoring/adversarial merge pass before findings count. `verify_depth=="light"`
(TRIVIAL/SMALL at low/normal stakes) was explicitly left out of scope, to
protect PRD G14/G15's complexity-adaptive efficiency goals. The epic design
deliberately deferred the exact lens count and dimension-to-lens assignment
to this child ticket.

## Decision

1. `code-verifier.md` gains a new dimension 14, "Regression-risk
   (git-history)" — full-depth only — appended after dimension 13
   ("Audience-style") with dimensions 1-13 left byte-for-byte unchanged.
2. The now-14 dimensions are split into exactly **4 fixed lenses**, each
   reading a distinct evidence source:
   - **Lens A — Correctness & Acceptance** (dimensions 1, 2, 3, 4, 5): the
     branch diff + `ticket.json` re-read fresh; the ONLY lens that re-runs
     the test/coverage/e2e suite.
   - **Lens B — Security, Standards & Craftsmanship** (dimensions 6, 7, 10,
     12): the branch diff + `standards/` at `standards_path` when
     configured; no suite re-run.
   - **Lens C — Architecture & Documentation** (dimensions 8, 9, 11, 13):
     the branch diff + `design.md` + `architecture_path` +
     `requirements_path` + `prd.md`/`roadmap.md` + the plan artifact's
     prose; no suite re-run.
   - **Lens D — Regression-risk** (dimension 14): the branch diff + git
     history on touched paths (bounded lookback); no suite re-run.

   This split is a fixed literal documented directly in `code-verifier.md` —
   no settings key configures lens count or assignment.
3. `code/SKILL.md`'s "Verify (per iteration)" section branches on
   `verify_depth`:
   - `"full"`: the coordinator spawns 4 parallel `acs:code-verifier`
     subagents, each carrying `<constraint name="verify_lens">A|B|C|D
     </constraint>`, each writing its own
     `iter-<n>-verify-lens-<A|B|C|D>.md` artifact. After all 4 return, the
     coordinator (never a subagent) performs the merge: a finding raised by
     2+ lenses is corroborated and stays blocking; a finding raised by
     exactly 1 lens is adversarially re-scrutinized by the coordinator
     itself against the cited evidence — confirmed stays blocking,
     unconfirmed downgrades to `severity="info"` with rationale, never
     silently dropped. The coordinator writes the single merged
     `iter-<n>-verify.md`. Zero surviving blocking findings = pass,
     unchanged from today's rule.
   - `"light"`: unchanged — exactly one `acs:code-verifier` spawn, no
     `verify_lens`, checking all 13 base dimensions, writing
     `iter-<n>-verify.md` directly.
   - The in-loop escalation check's trigger (a) reads the coordinator's
     FINAL merged findings list for full depth; the merge write always
     happens before the next iteration's trigger-(a) evaluation.
4. Only Lens A re-runs the test/coverage/e2e suite — Lenses B/C/D never
   duplicate a suite run — bounding the cost multiplier to 4x verifier
   spawns per full-depth iteration, not 4x suite runs.

## Consequences

**Accepted cost:** full-depth tickets now spawn 4 verifier subagents per
verify iteration (up to 3 iterations) instead of 1 — a real cost/latency
multiplier, contained by the suite-reuse rule in Decision 4 (design.md Risk
R5).

**Positive consequence:** a full-depth verify pass gets a
generate-then-adversarially-filter shape — independent lenses cannot
rubber-stamp each other's blind spots, and a single-lens claim is no longer
enough to block on its own without the coordinator's independent
confirmation.

**Zero functional change to light depth:** no edit touches any text path
reached only when `verify_depth=="light"` or when `verify_lens` is absent —
light-depth tickets keep today's single-subagent-with-internal-adversarial-
pass shape and 1-iteration ceiling, protecting PRD G14/G15's
complexity-adaptive efficiency goals.

**Retired dimension unaffected:** create-spec-verifier's retired
`consistency` dimension (ADR 0066) stays retired; the 4-lens split
introduces no new cross-file consistency surface — each lens still judges
the same single combined changeset, only from a narrower evidence subset.
