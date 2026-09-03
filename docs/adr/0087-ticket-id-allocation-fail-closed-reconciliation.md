# 0087 — Ticket-id allocation: fail-closed reconciliation gate

**Status**: Accepted · **Date**: 2026-09-02

## Context

`allocate_ticket_id` (`acs_lib.py`) mints the next `<prefix>-<n>` id from
`counters.json`'s `next` field with no cross-check against reality. A fresh
or previously-unreconciled workspace partition — the default state for any
new repo, new clone, or newly-configured `workspace_path` (ADR-0086) — starts
`next` at 1 regardless of what ids the repo's own history already carries,
so the very first allocation can silently mint an id that collides with one
already used in that repo. This defect class caused a real near-miss in this
same session: a fresh workspace's counter was about to mint a colliding
`MAR-1` against a repo already at `MAR-401`.

Three options were weighed for reconciling a fresh partition's floor before
its first allocation:

- **Reconcile from the tracker.** The tracker is the only source that knows
  the true highest id. Rejected: it requires network access precisely in the
  session class this defect targets (measured, in this session, `gh api
  repos/globalmindsolution/gms-marketplace` exits 1), it violates the
  network-free constraint on id allocation, and matching `<prefix>-<n>`
  against tracker issue numbers is unsound — GitHub issue numbers are a
  different numbering space from acs ticket ids.
- **Bare fail-closed gate, no evidence.** The first allocation from an
  unreconciled partition refuses with exit 2 until a human supplies a
  number, with no proposal to confirm. Network-free and deterministic, but a
  prompt asking a human to invent a number from nothing gets answered
  wrongly or clicked through — a gate always rubber-stamped is a gate in
  name only.
- **A git-committed high-water-mark file.** A tracked file recording the
  highest minted id, read by a fresh workspace to seed itself. The only
  option that helps a second clone on a different machine with no prompt at
  all, and it would have prevented the near-miss above. Rejected: it puts
  pipeline state into the consumer repo (state lives in the gitignored state
  root by design), it is accurate only once the minting commit reaches the
  default branch — so an id minted on an unmerged branch is invisible to a
  parallel clone, the exact concurrent case that matters — and it becomes a
  merge-conflict hotspot across the parallel worktrees the counter's own
  O_EXCL guard exists to serialize. Recorded as a possible future
  *additional* evidence source; nothing in this decision forecloses it.

## Decision

Combine the fail-closed gate with a deterministic, network-free local-evidence
scan that computes a **proposed floor**, confirmable rather than
authoritative: the script proposes, a human confirms, the script writes.

- **The gate.** Inside `allocate_ticket_id`'s existing O_EXCL critical
  section (between guard acquisition and the counter write, so two parallel
  worktrees can never both observe "unreconciled" and both seed), absent
  both `next` and `reconciled: true` in `counters.json`, the call raises
  `ReconciliationRequired` (a `GateError` subclass) instead of minting — both
  call sites, `new-ticket.py` and `skill-start.py --allocate` (including its
  product-level-skill path), translate that to **exit 2** with actionable
  stderr. An already-populated `counters.json` (`next` present, or
  `reconciled: true`) is treated as already reconciled: no prompt, no scan,
  no new keys written — this is what keeps the change invisible to every
  existing repo.
- **The evidence proposal.** `scan_local_ticket_evidence` runs three ranked,
  network-free sources, shelling out only to `git`: committed-files grep
  (`git grep -I -E`, tracked files only), then git commit subjects+bodies
  (`git log --format=%s%n%b -400`), then branch names
  (`git for-each-ref --count=400`). `observed_max` is the **maximum over all
  three sources** — not a first-hit-wins walk — with the rank order serving
  as the tie-break and `seed_source` provenance label, since a higher floor
  never increases collision risk. Each source is bounded to 400 commits/refs,
  tracked-files-only scope, and a 10-second per-subprocess timeout (the
  timeout `acs_lib._git` already ships), for a ≤30-second worst case, once
  per partition, on the refusal path only — never on a `pre-<skill>.py` gate
  path. A timeout, non-zero exit, or absent git repo degrades that source to
  nothing and the next rank is tried; if all three yield nothing, the
  refusal still fires with "no local evidence found" wording. A timeout
  degrades the prompt, never the gate.
- **Confirmed reconciliation is recorded**, not merely acted on: additive,
  optional `counters.json` fields — `reconciled` (boolean), `seed_source`
  (`committed-files`\|`git-history`\|`branch-names`\|`explicit-user`),
  `seeded_at` (ISO-8601 UTC) — all valid today under the schema's existing
  `additionalProperties: true`, with `required` staying `["next"]`. The
  evidence scan's `observed_max` is surfaced only in `ReconciliationRequired`'s
  refusal message, for a human to read — it is never persisted to
  `counters.json`.
- **`--seed-next <n>`** is added to both `new-ticket.py` and
  `skill-start.py --allocate`, as one flag serving two roles: it is the
  *confirm* answer to a refusal's proposal, and the *recovery* path when a
  reconciliation state is wrong or stuck — minting `<PREFIX>-n` immediately
  and writing `next=n+1`, `reconciled=true`, `seed_source=explicit-user`,
  `seeded_at=now` (so the *next* mint after this confirm is `<PREFIX>-(n+1)`,
  not `<PREFIX>-n` again), with no workspace state deleted. Both CLIs gain
  the flag so neither `allocate_ticket_id` call site is a dead end regardless
  of which one triggers the refusal.

Local evidence is a **floor, not the truth** — the tracker may hold higher
ids than any local source can observe — which is why the proposal must stay
confirmable rather than authoritative, and why the gate fails closed on no
evidence rather than defaulting to 1.

This decision is scoped to the reconciliation gate only. The sibling
decision on `gh` as acs's sole GitHub transport and its call-criticality
classification, split from the same parent epic (MAR-401), ships separately
as ADR-0088.

## Consequences

**Positive**: a fresh or unreconciled workspace partition can no longer
silently mint a colliding id — the exact defect class that produced this
session's near-miss. Existing, already-populated repos see no behavior
change: byte-identical allocation, no prompt, no new keys.

**Accepted cost**: friction on every genuinely new repo's and every fresh
clone's *first* allocation for a given `(repo_id, prefix)` pairing — by
design, since a gate always answered automatically is not a gate. A
fan-out run that starts several `skill-start.py --allocate` legs at once
against a fresh partition sees every leg refuse simultaneously; this is
correct fail-closed behavior, and the first successful `--seed-next`
reconciles the partition for every later leg.

**Known limitation, accepted**: the local-evidence proposal's quality is
repo-dependent and unknowable to the scanner — a repo with a per-ticket
CHANGELOG proposes close to the truth, a repo without one can fall through
to a floor dozens of ids short. The gate is correct either way because the
proposal is confirmable, never authoritative, and the human — not the
scanner — is the source of truth for the number actually written.
