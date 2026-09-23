# The `## Contract` block — who reads each field, and why

The block's SHAPE is in `create-impl-plan/SKILL.md`, because every plan writes
it. This file is the per-field reasoning: open it when a value is not obvious,
in particular before recording `delivery_path`.

Three readers, three reasons:

- **`delivery_path`** — `trivial | small | standard | complex`, judged ONCE,
  here, from the plan's own scope (`skills/code/references/classify.md` is the
  rubric). `/acs:code` dispatches to its leg from it; nobody picks a path by
  hand and nothing re-judges it. Prefer the more expensive path whenever two
  fit: an unnecessary lens pass costs tokens, a missed regression in a
  load-bearing path costs more.
- **`owes`** — whether `/acs:create-api-contract`, `/acs:create-test-docs` and
  the e2e steps have work on this run. Each of those steps reads its own flag
  and records an evidenced no-op when the answer is false; **silence is not
  permission to skip**, so a step whose flag is absent does its work and
  decides for itself. `reason` is one sentence a reviewer can check.
- **the file map** — the executor partition, and the contract the file-map
  guard enforces on every Write. `### Executor tasks & file map` keeps its
  exact heading because the guard and `plan-approval.py` already key on it.

`plan_sha256` hashes the whole file, prose and contract alike, so editing
either invalidates the approval. A skill that needs a value reads the
`## Contract` block and nothing else; a human reads everything above it and
need not read the block at all.
