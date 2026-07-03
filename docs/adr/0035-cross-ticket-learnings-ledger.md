# 0035 — Cross-ticket learnings ledger: repo-tier append-only JSON with substring triggers, distilled at merge, injected bounded at skill-start, provisional entries never steer agents

**Status**: Proposed · **Date**: 2026-07-03

## Context

The acs pipeline is multi-session: `create-ticket → create-spec → code →
create-pr → merge-pr` each may run in a fresh session with no memory of prior
runs. Every fresh session re-derives the same repo-specific facts (convention
gate exact-header behavior, coverage target, paid e2e command, architectural
boundaries) by re-reading files and repeating investigations a prior session
already finished. This re-derivation is the dominant avoidable token cost across
a ticket's arc — the concern that prompted this design.

The existing `clarify.py` clarification ledger already solves the *within-ticket*
version of this (never re-ask an answered question). What is missing is its
*cross-ticket* sibling: a repo-scoped memory that survives ticket archival.

The problem is **persistence**, not **semantic search**. There is a small,
growing set of exact reusable facts to remember verbatim. A vector/embedding
retrieval layer would add an embedding model, an index-freshness problem, and a
per-retrieval token tax to approximate-match facts that should be matched
exactly — a solution mismatched to the problem, and one that breaks acs's
stdlib-only deterministic-helper constraint (ADR 0003 file-based state; the
clarify/metrics helpers are all stdlib).

## Decision

Introduce a repo-tier **learnings ledger**.

1. **State — `learnings.json` at the repo tier**, at
   `repo_dir(workspace, repo_id)/learnings.json`, keyed by `repo_partition_id`,
   beside `tickets-index.json`/`metrics.json`/`counters.json`. Because `archive/`
   is a subdirectory of the repo dir, archiving a ticket never mutates the
   ledger — it survives archival by construction. Append-only; atomic writes via
   `lib.write_json`.

2. **Helper — `learn.py`**, cloned from `clarify.py` (same
   `build_context → resolve ticket → resolve path → atomic write` skeleton).
   Subcommands `add`, `promote`, `list`. No new always-on hook.

3. **Entry shape** — atomic, evidence-linked: `id`, `kind`
   (`convention|pitfall|architecture|tooling`), `trigger` (substring key),
   `lesson`, `evidence` (`{ticket, finding}`), `confidence`, `seen_tickets`,
   timestamps. A lesson is never written without evidence.

4. **Confidence ladder** — `provisional` (1 ticket) → `established` (auto, at ≥2
   distinct `seen_tickets`) → `core` (human `learn.py promote`).

5. **Safety invariant (load-bearing): a `provisional` learning is NEVER injected
   into any agent context.** Injection begins at `established`. A lesson cannot
   steer agents until a second independent ticket confirms it (or a human
   promotes it). This removes the self-steering failure mode where an agent
   invents a lesson and then obeys its own unverified hallucination next session.

6. **Capture — distillation at merge, before archival.** The `/acs:merge-pr`
   coordinator reads the ticket's `clarifications.json` + verifier findings and
   `learn.py add`s reusable facts. Bounded at **3 candidates per merge**; excess
   is dropped with a `log()` (no silent truncation). `/acs:code` may add
   `provisional` entries opportunistically. De-dup on
   `(kind, trigger, normalized-lesson)` appends `seen_tickets` and bumps
   confidence rather than duplicating.

7. **Consume — bounded injection at skill-start, default on.**
   `skill-start.py` calls `learnings_digest(ctx, ticket)` and adds a
   `"learnings"` field to the context JSON it already prints (no new round-trip).
   Selection: `established`/`core` only, `trigger` substring-matches current
   context, ranked confidence-then-recency, top **K=7** with a hard character
   cap. Opt-out via `settings.learnings.{enabled,max_entries}`.

## Alternatives considered

- **Vector / embedding retrieval over tickets+specs+designs:** the semantic-search
  framing. Rejected for v1: the problem is exact-fact persistence, not fuzzy
  lookup; it adds an embedding model, index freshness, and a retrieval token tax;
  and it breaks the stdlib-only constraint. May be revisited behind a settings
  opt-in if substring triggers prove too blunt in practice.
- **Inject provisional (1-ticket) learnings too:** maximizes recall but
  reintroduces the ECC self-steering risk — a single session's unverified claim
  steers all future sessions. Rejected; the 2-ticket / human-promote floor is the
  safety mechanism.
- **A new always-on Stop/PostToolUse hook to capture learnings continuously:**
  more capture surface, but adds a hook to every turn and captures noise.
  Rejected in favor of capturing at merge, when the work is validated and the
  context is hot.
- **Per-ticket storage (like clarifications):** would not survive archival and
  could not be shared across tickets — defeats the purpose. The ledger must be
  repo-tier.
- **Default-off injection:** safest, but defers the entire token benefit
  indefinitely while a human watches the ledger fill. Rejected in favor of
  default-on **bounded** injection, since the provisional-never-injected rule and
  the hard K/char caps already contain the risk.

## Consequences

- New repo-tier file `learnings.json` and helper `learn.py` (~140 lines, cloned
  from `clarify.py`). No changes to existing state-file shapes.
- `skill-start.py` gains a `"learnings"` field in its context JSON; every
  coordinator that reads that JSON gets the digest for free. Behavior is bounded
  and opt-outable.
- `/acs:merge-pr` gains a distillation step before archival; `/acs:code` gains an
  opportunistic capture path. Both are additive.
- The provisional-never-injected invariant is a tested code fact, not just prose.
- Ships as an epic through acs's own pipeline (dogfooding). The epic's
  create-design step may supersede/extend `docs/design/learnings-ledger.md`.
- Supersedes the stale memory note that placed this at "ADR 0013" — that slot is
  occupied on disk by the metrics ADR; this is a fresh number.
