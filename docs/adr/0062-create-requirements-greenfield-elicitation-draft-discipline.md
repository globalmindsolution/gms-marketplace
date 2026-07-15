# 0062 — `/acs:create-requirements` greenfield elicitation + uniform DRAFT discipline

**Status**: Accepted · **Date**: 2026-07-15

## Context

ADR 0061 built `/acs:create-requirements` with two working modes —
**brownfield** (reverse-engineer the requirements set from an existing
codebase) and **amend** (augment an already-populated set) — and deliberately
**deferred greenfield**: on a repo with no meaningful codebase AND an absent
requirements set, the planner classified the case but returned
`status="needs_input"` with a "ships in a subsequent increment" notice rather
than attempting a half-built elicitation. That deferral is what this decision
closes. The output is behavioral-requirements PROSE grounded in the user's
answers (there is no code to cite), inherently LLM-driven like
`/acs:create-prd`'s greenfield elicitation, so the elicitation mechanism and
the confirm discipline that governs it both need settling before the mode is
turned on.

## Decision G1 — greenfield elicitation: mirror create-prd's greenfield producer

**Selected.** The greenfield mode is a real elicitation branch across the four
create-requirements markdown files, mirroring `/acs:create-prd`'s greenfield
shape rather than inventing a new pattern:

- the **planner** classifies greenfield (no meaningful codebase to
  reverse-engineer AND the set is absent) as one of a clean three-way split
  (brownfield / greenfield / amend), and plans the elicitation — per candidate
  feature area, the behavior it must have (a functional requirement); per
  candidate quality concern, the constraint it must meet (a non-functional
  requirement) — never silently falling through to brownfield;
- the **coordinator** elicits from the user and confirms the DRAFT baseline via
  the same clarify-ledger / interactive-confirm mechanism used for
  brownfield/amend, batching questions and proposing drafts to confirm when
  `$ARGUMENTS` already carries notes;
- the **executor** writes one `<functional_subdir>/<feature>.md` per elicited
  behavioral feature and one `<non_functional_subdir>/<item>.md` per elicited
  NFR item, DRAFT-marked, each clause grounded in and cited to the user's
  answer (no code-citation is required or expected — there is no code to cite);
- the **verifier** re-checks the mode as an elicited set: "coverage" diffs the
  produced files against the plan's elicitation outline (there is no codebase to
  re-enumerate), and "citation" traces every clause to a specific user answer in
  the clarify ledger rather than a repo file/path — the same blocking bars as
  brownfield, retargeted to the elicitation evidence source.

Rejected alternatives:

- **G2 — keep greenfield deferred (a `needs_input` handoff).** Rejected — it
  leaves G37 without the greenfield bootstrap path the epic requires, and a
  standing "recognized but not built" branch is a permanent papercut.
- **G3 — a greenfield-only fourth agent / separate skill.** Rejected — the
  elicitation reuses the existing triad's charter almost verbatim (only the
  evidence source differs), so a fork would duplicate the coverage / citation /
  DRAFT / routing machinery for no behavioral gain.

## Decision G4 — uniform DRAFT / interactive-confirm discipline across all three modes

**Selected.** A produced requirement — elicited (greenfield), extracted
(brownfield), or augmented (amend) — is a **DRAFT baseline, never authoritative
without confirmation**: every produced area file opens with the
`DRAFT — human-confirm-required` marker, open points are surfaced for
confirmation, and the interactive-confirm step MUST complete before the
executor is spawned. The discipline is stated once, uniformly, rather than
per-mode, so no mode can drift into auto-authoring an authoritative contract
without the human gate (C-22). The per-file format is finalized as the
functional/non-functional model itself — the DRAFT marker line, then the
existing living-requirements `MUST`/`SHOULD`/`MAY`/`[OPEN]`/`[ASSUMPTION]`
prose, with no fixed universal heading skeleton and no new template file
(design Decision B-revised).

## Consequences

- Greenfield is now a first-class mode: `/acs:create-requirements` offers the
  full three-mode set (brownfield / greenfield / amend), completing the G37
  bootstrap path. The prior "greenfield deferred to MAR-144" language is
  removed from all four skill/agent files.
- The elicitation engine is coordinator + agent-charter PROSE reusing the
  existing triad (mirrors `create-prd`'s greenfield mode) — no new agent, no
  new skill, no new stdlib helper, no new settings key ships with this decision.
- The DRAFT / human-confirm-required, interactive-confirm gate is uniform
  across all three modes; nothing this skill produces is authoritative until the
  user confirms it (C-22).
- Requirements stays a **living contract** alongside the verified conformance
  chain (`PRD → architecture → principles → standards → design → specs →
  code`) — this decision adds **no** requirements-conformance verifier
  dimension to `/acs:create-spec` or `/acs:code`, and does not touch the chain
  line in `docs/architecture/lld/contracts.md`; it only completes the
  clarifying living-contract note there (Decision D1, ADR 0060/0061).
- **ADR numbering.** ADR 0061 recorded that MAR-145 took **0060** and
  reverse-engineer producer took **0061**, leaving 0058/0059 as deliberate
  gaps below the high-water mark. This ADR uses the next-free-**above-max**
  id, **0062** (the design originally reserved "0059"; superseded), keeping
  ADR numbering chronologically monotonic — 0058/0059 stay unused.
