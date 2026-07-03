# Design: The Learnings Ledger

**Status:** Proposed
**Date:** 2026-07-03
**Author:** brainstormed with Claude Code
**ADR:** [0035-cross-ticket-learnings-ledger](../adr/0035-cross-ticket-learnings-ledger.md)
**Branch:** `design/learnings-ledger` (local; not pushed)

## Problem

The acs pipeline is multi-session by construction: `create-ticket → create-spec →
code → create-pr → merge-pr` may each run in a fresh session. Every fresh session
re-derives the same repo-specific facts — "the PR convention gate greps for exact
section headers", "coverage is enforced at N%", "this repo's e2e command is paid" —
by re-reading files and re-running the same investigations a prior session already
completed. That re-derivation is the dominant avoidable token cost across a
ticket's arc.

Semantic search / vector retrieval does **not** solve this. The pain is
*persistence*, not *fuzzy lookup*: there is a small, growing set of exact,
reusable facts that should be remembered verbatim, not approximately matched.
A plain append-only JSON with substring triggers is the right shape and honors
acs's stdlib-only, deterministic-helper constraint (no embedding model, no index
freshness problem, no retrieval token tax).

## Non-goals

- Semantic / embedding retrieval (deferred; see ADR 0035 "Alternatives").
- A new always-on hook. Capture and injection both ride existing surfaces.
- Per-user or cross-repo memory. The ledger is repo-scoped only.
- Replacing the per-ticket clarification ledger (`clarify.py`) — the learnings
  ledger is its cross-ticket sibling, distilled from it at merge.

## Architecture & placement

The ledger lives at the **repo tier**, keyed by `repo_partition_id`, beside the
other repo-tier state:

```
<workspace>/<repo_id>/
├── tickets-index.json      (exists)
├── metrics.json            (exists)
├── counters.json           (exists)
├── learnings.json          (NEW — append-only, survives ticket archival)
├── <MAR-N>/…               (per-ticket partitions)
└── archive/…               (archived tickets — a subdirectory, so archival
                              never touches learnings.json)
```

Path: `repo_dir(workspace, repo_id)/learnings.json` (via the existing
`acs_lib.repo_dir` helper). Because `archive/` is a *subdirectory* of the repo
dir, archiving a ticket cannot delete or mutate the ledger — this is what
"survives archival" means concretely.

**Helper:** `learn.py`, cloned from `clarify.py`. Same skeleton:
`build_context(cwd) → resolve ticket id → resolve path → atomic
lib.write_json`. ~140 lines. Three subcommands: `add`, `promote`, `list`.

**No new always-on hook.** Capture rides the `/acs:merge-pr` and `/acs:code`
coordinators. Injection rides the `skill-start.py` context JSON that every
coordinator already reads as its first action.

## Data shape

`learnings.json`:

```json
{
  "repo_id": "globalmindsolution-autonomous-coding-skills",
  "learnings": [
    {
      "id": "L-7",
      "kind": "convention | pitfall | architecture | tooling",
      "trigger": "pr-conventions.py",
      "lesson": "PR body must contain the four sections named in settings.enforcement.pr_description_sections; the gate greps for exact headers.",
      "evidence": {"ticket": "MAR-3", "finding": "verifier-iter-2"},
      "confidence": "provisional | established | core",
      "seen_tickets": ["MAR-3"],
      "created_at": "2026-07-03T12:00:00Z",
      "updated_at": "2026-07-03T12:00:00Z"
    }
  ]
}
```

Field notes:

- **`trigger`** — a substring key. At injection time `learn.py` selects entries
  whose `trigger` appears in the current ticket/skill context string. v1 is
  substring-only (no embeddings).
- **`kind`** — coarse category, for display grouping and future filtering.
- **`evidence`** — links the lesson back to the originating ticket + finding so a
  human can audit *why* a lesson exists. Never write a lesson without evidence.
- **`confidence`** — the safety ladder (below).
- **`seen_tickets`** — distinct tickets that produced/confirmed this lesson;
  its length drives auto-promotion `provisional → established`.

### Confidence ladder & the injection safety rule

```
provisional  ── seen in 1 ticket. Captured, listed, NEVER injected to steer agents.
     │  (auto) reaches ≥2 distinct seen_tickets
     ▼
established   ── injectable. Auto-promoted when a second distinct ticket confirms it.
     │  (human) `learn.py promote --id L-n --to core`
     ▼
core          ── injectable, top priority. Human-vouched; survives pruning.
```

**Safety invariant (the load-bearing rule): a `provisional` learning is NEVER
injected into any agent's context.** It is only recorded and human-listable.
Injection begins at `established`. This removes the ECC-style self-steering
failure mode: an agent cannot invent a "lesson" in one session and then obey its
own unverified hallucination in the next — a second, independent ticket must
confirm it first (or a human must promote it).

## Capture (write path)

1. **Primary — distillation at merge, before archival.** The `/acs:merge-pr`
   coordinator, as part of its finalize-before-archive step, reads the ticket's
   `clarifications.json` and verifier findings and calls `learn.py add` for
   genuinely reusable, repo-general facts. Merge is the correct moment: the work
   is validated, and it is the last point at which the ticket's context is hot.
2. **Opportunistic — during `/acs:code`.** When a verifier iteration surfaces a
   repo-specific gotcha, the coordinator may `learn.py add` it as `provisional`.
   (Provisional, so it does not steer anything until a second ticket confirms.)

**Bound:** at most **3** candidate learnings captured per merge. When more
qualify, the coordinator keeps the highest-evidence three and `log()`s that the
rest were dropped — no silent truncation.

De-dup: `learn.py add` compares `(kind, trigger, normalized-lesson)` against
existing entries; a match appends the current ticket to `seen_tickets` and bumps
confidence per the ladder rather than creating a duplicate row.

## Consume (read path — the token win)

`skill-start.py` calls a new bounded `learnings_digest(ctx, ticket)` and adds a
`"learnings"` field to the context JSON it already prints. **No new round-trip** —
it piggybacks on a payload every coordinator already reads as step one.

Selection is bounded and deterministic:

- Only `established` and `core` entries (never `provisional`).
- Only entries whose `trigger` substring-matches the current context
  (ticket title/type/skill + settings surface).
- Rank by confidence (`core` > `established`) then recency (`updated_at`).
- Top **K = 7**, with a hard character cap so a runaway ledger can never bloat
  the digest.

**Default on, bounded.** This is the behavioral change that touches every
session; it is contained by (a) the provisional-never-injected rule and (b) the
hard bounds. Opt-out via settings:

```json
"learnings": { "enabled": true, "max_entries": 7 }
```

### Why this answers the original token concern

Instead of a fresh session re-reading files to re-derive "the PR gate wants exact
headers", that fact is one selected line in a bounded digest — tens of tokens,
delivered inside a payload the session already fetches, versus a multi-file
investigation repeated every ticket.

## Testing

Clone `clarify.py`'s test file and cover:

- round-trip `add` / `promote` / `list`;
- confidence transitions: `provisional → established` at the 2nd distinct
  `seen_tickets`, and human `→ core`;
- **the safety invariant**: `learnings_digest` never returns a `provisional`
  entry, under any input;
- bound enforcement: ≤3 captured per merge; ≤K=7 and char-cap on the digest;
- atomic-write safety (no partial JSON on concurrent writers) — mirror the
  clarify ledger's approach;
- de-dup: re-adding an equivalent lesson appends `seen_tickets`, does not
  duplicate.

Behavioral evals remain local-only per ADR 0022 (no LLM calls in CI).

## Rollout

Ship as an **epic through acs's own pipeline** (dogfooding):
`create-ticket → create-design → create-spec → code`. The create-design step of
that epic may supersede or extend this document; ADR 0035 records the decision.

This design work itself is committed **local-only** on branch
`design/learnings-ledger` and is intentionally **not pushed** — it is the
brainstorm artifact, not the implementation PR.

## Open questions (for the epic's create-design step)

- Auto-retire: should an `established` learning that stops matching for N
  tickets decay back toward `provisional`, or is the ledger append-only forever
  with only manual pruning?
- Capture cap: is 3/merge right, or should it scale with ticket size/lane?
- Trigger matching: substring-only in v1 — revisit only if substring proves too
  blunt in practice (still no embeddings without a settings opt-in).
