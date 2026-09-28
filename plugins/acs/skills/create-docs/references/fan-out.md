# /acs:create-docs — running more than one set

Open this when the eligible batch Start handed you holds **more than one
set** — the `all` request, or a comma-separated list. A single-set run and
every resume-by-ticket-id run skip all of it: there is no slice to cap, no
second worktree to keep apart, and no sibling run to isolate a failure from.

## Concurrency cap

Never run every set at once: run **at most 2** sets concurrently. That cap is
this skill's own — `ship.yaml` carries no `max_parallel` since ADR-0096 — and
the Start snippet prints it as `max_parallel`. Walk each batch
`fanout_batches` returns in **slices of at most `max_parallel`** sets,
finishing one slice's sets before starting the next. Everything below that
says "this slice" means those at-most-`max_parallel` sets.

The cap bounds instances per phase too. The Author message spawns at most
`max_parallel` authors (one per set). The Review message spawns every
**dimension slice** of every set in this slice — two per set
(`SKILL.md` → Review), so at most 2 × `max_parallel` = **4** reviewer
instances, the per-phase fan-out cap. A dimension slice is not a set slice:
it splits one set's review, never the batch.

## Worktrees — one per set, created before that set's Start

For every set in this slice, create one git worktree outside the consumer
repo (`docs/requirements/functional/workspace-and-state.md`'s
worktree-per-unit-of-work convention), with a **generic, set-scoped**
directory name — never ticket-id-named, because the delivery ticket id does
not exist until that set's Start runs:

```bash
git worktree add --detach <path> <default-branch>
```

The `--detach` form is required: the session checkout already has
`<default-branch>` checked out, so a plain `git worktree add <path>
<default-branch>` fails outright (`fatal: '<default-branch>' is already used
by worktree at …`). `--detach` leaves the new worktree at the branch tip with
`git status --porcelain` empty, which is exactly the clean-tree precondition
the set's Branch step needs. Once that set's Start has minted its ticket id,
enter its worktree and run Delivery step 1 (Branch) there — **before the
Author phase** — so every subsequent write for that set (the author's doc
writes and Delivery steps 2-4) happens inside that worktree on that branch;
each author's `<task>` carries that set's worktree-absolute output paths, so
its writes cannot land in the session checkout. A single-set run may skip the
worktree and use the session checkout, provided the clean-tree precondition
holds.

## Failure isolation — per set

Every failure is isolated to its own set — a reviewer cap reached at
iteration 3, a lock held by another session, a refused push. The failing
set's run status, ticket, partition and lock are its own; every OTHER set's
run, PR and ledger are never touched by it. Report each set's outcome
independently, each with its own resume command
(`/acs:create-docs <delivery-ticket-id>`). The one shared upstream input, the
architecture doc set, was looked for at Start before any set started, and its
absence refuses nothing — it only changes what each author grounds on — so
there is no shared failure left to carve out.
