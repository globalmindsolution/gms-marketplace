# Flow — Ticket-id first-allocate reconciliation

`allocate_ticket_id` (`acs_lib.py`) gains a fail-closed, network-free
reconciliation gate inside its existing O_EXCL critical section (MAR-402).
The first allocation for a `(repo_id, prefix)` partition that has never
allocated an id refuses with exit 2 unless a confirmable local-evidence
proposal is confirmed by a human; an already-populated `counters.json` is
treated as already reconciled, with no prompt and no scan. Both call sites —
`new-ticket.py` and `skill-start.py --allocate` (including its
product-level-skill path) — reach the same gate, so neither can silently
bypass it.

## Sequence — refusal, evidence scan, confirm, and steady state

```mermaid
sequenceDiagram
    autonumber
    participant CALLER as new-ticket.py or skill-start.py --allocate
    participant ALLOC as acs_lib.allocate_ticket_id
    participant LOCK as counters.json.lock guard
    participant CJ as counters.json
    participant EV as scan_local_ticket_evidence (network-free)
    participant USER as User

    CALLER->>ALLOC: workspace, repo_id, prefix, repo_root, seed_next
    ALLOC->>LOCK: O_EXCL create, bounded spin, stale guard removed
    LOCK-->>ALLOC: guard acquired
    ALLOC->>CJ: read counters

    alt seed_next is not None
        Note over ALLOC,CJ: authoritative confirm/recovery path
        ALLOC->>CJ: write next=seed_next, reconciled=true, seed_source=explicit-user, seeded_at=now
        ALLOC-->>CALLER: mint PREFIX-seed_next, increment
    else next present, or reconciled is true
        Note over ALLOC,CJ: already reconciled — existing/migrated repos never prompted, no scan, no new keys
        ALLOC->>CJ: write next incremented by one
        ALLOC-->>CALLER: ticket id
    else next absent and reconciled not true
        Note over ALLOC: fail-closed — nothing written, no id minted
        ALLOC->>EV: rank 1 committed-files grep (git grep -I -E, tracked files only)
        EV-->>ALLOC: highest id observed, or nothing (timeout/no-git-repo/non-zero exit)
        ALLOC->>EV: rank 2 git-history (git log --format=%s%n%b -400)
        EV-->>ALLOC: highest id observed, or nothing
        ALLOC->>EV: rank 3 branch-names (git for-each-ref --count=400)
        EV-->>ALLOC: highest id observed, or nothing
        Note over EV: observed_max is the maximum over all three sources, seed_source is the lowest-ranked source that observed it, all three empty degrades to "no local evidence"
        ALLOC-->>CALLER: raise ReconciliationRequired(prefix, repo_id, observed_max, seed_source, proposed_next)
        CALLER->>USER: exit 2, actionable stderr — blocked+why, the local-evidence floor (or "no local evidence"), the exact --seed-next <n> recovery command
        USER->>CALLER: confirms the first id to mint
        CALLER->>ALLOC: re-run with --seed-next <n>
        Note over ALLOC,CJ: re-entry takes the seed_next arm above, inside a fresh guard acquisition
    end
    ALLOC->>LOCK: release guard in the finally arm, on every path including the refusal
```

Local evidence is a **floor, not the truth** — the tracker may hold higher
ids than any local source can observe, which is why the proposal is always
confirmable, never authoritative, and why the gate fails closed on no
evidence rather than defaulting to 1.
