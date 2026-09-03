---
name: create-docs
description: Detect independent doc-bootstrap skills (currently create-quality and create-operations) whose upstream prerequisites are already satisfied, and fan them out in parallel instead of running them one after another — each leg keeps its own hooks, reflection cycle, and gating unchanged, and delivers as its own docs-only PR on its own delivery ticket. Use instead of running /acs:create-quality and /acs:create-operations sequentially.
argument-hint: "[--for <skill>[,<skill>...]]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-docs — an unhooked umbrella, exactly
like `/acs:ship`, `/acs:test`, and `/acs:release`: you have no
planner/executor/verifier of your own, and you never write a doc file
yourself. You detect which doc-bootstrap skills are eligible for parallel
fan-out this pass, run each eligible skill's own Start **sequentially** as a
genuine Skill-tool call (so every existing hook fires exactly as it would
standalone), and then drive both legs' reflection loops together from your
own context by spawning each phase's subagents in parallel batches.

Ground rules, non-negotiable:

- Every fanned-out skill's own hooks (pre/post), reflection cycle
  (planner/executor/verifier), and gating fire unchanged. You add
  orchestration only — you never bypass, simulate, or duplicate a hook.
- You have no planner/executor/verifier of your own. Each fanned-out skill
  runs its OWN reflection cycle via its OWN existing agent files
  (`acs:create-quality-planner/-executor/-verifier`,
  `acs:create-operations-planner/-executor/-verifier`), which you spawn
  directly with the Agent tool — you never do a leg's work yourself.
- v1's eligible set is exactly `create-quality` + `create-operations`
  (D7-A) — a third doc-bootstrap skill becoming fan-out-eligible later is a
  data change, not a code change: it must be added to ALL FOUR of
  `acs_lib.DOC_BOOTSTRAP_DEPENDENCIES`, `acs_lib.DOC_BOOTSTRAP_FANOUT_V1`,
  `acs_lib.DOC_BOOTSTRAP_SETTINGS_KEY`, and `acs_lib.DOC_BOOTSTRAP_SENTINEL`,
  never an edit to this skill.
- This is not epic-child fan-out (`ship/SKILL.md`'s "Epic fan-out" section,
  unchanged) — that mechanism parallelizes *tickets* sharing one design;
  this skill parallelizes independent *product-level doc-bootstrap skills*
  that share no ticket and no design step.

## Start — eligibility detection

MANDATORY first action — resolve settings and the eligible batch:

```bash
python3 - "$ARGUMENTS" <<'PY'
import json, os, sys
sys.path.insert(0, os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "hooks", "scripts"))
import acs_lib as lib
cwd = os.getcwd()
args_text = sys.argv[1] if len(sys.argv) > 1 else ""
settings, _sources = lib.load_settings(cwd)
try:
    workspace = lib.validate_settings(settings, cwd)
except lib.GateError as exc:
    sys.stderr.write("acs create-docs: %s\n" % exc)
    sys.exit(2)
root = lib.checkout_root(cwd) or cwd
repo_id = lib.repo_partition_id(cwd)
tickets_index = lib.read_json(lib.index_path(workspace, repo_id)) or {}
requested, rejected = lib.parse_fanout_for_arg(args_text)
batches = lib.fanout_batches(settings, tickets_index, root, candidates=requested)
print(json.dumps({"workspace": workspace, "repo_id": repo_id, "checkout_root": root,
                  "requested": requested, "rejected": rejected, "batches": batches}, indent=2))
PY
```

`acs_lib.fanout_batches(settings, tickets_index, checkout_root)` is the
**declared, not inferred** eligibility predicate (AC-5): each doc-bootstrap
skill's dependency edges live in `acs_lib.DOC_BOOTSTRAP_DEPENDENCIES`
(`{"hard": [...], "soft": [...]}` per skill) — never a prose guess. With no
`candidates` argument, `fanout_batches` defaults to the declared v1 gate,
`acs_lib.DOC_BOOTSTRAP_FANOUT_V1` — the v1 fan-out set is that constant, a
data declaration, not a hardcoded prose claim. A candidate is eligible only
when its settings path is configured, its doc set has not already shipped
on disk (`doc_set_present_on_disk`, the D4.2(a) sentinel-file predicate —
the skill's own first output file, e.g. `test-strategy.md` for
`create-quality`), it has no open (non-`done`) delivery ticket already in
flight, and every **hard** dependency is unconfigured or already shipped. A
**soft** dependency (today, exactly `create-standards` → `create-principles`)
never makes a candidate ineligible on its own — it only ever excludes that
candidate from sharing the **same batch** as an eligible soft peer;
`create-standards` and `create-principles` are never started in parallel
with each other, even though neither is in the v1 pair.

No arguments: fan out whatever `fanout_batches` returns for the declared
`DOC_BOOTSTRAP_FANOUT_V1` set. `--for <skill>[,<skill>...]`: fan out exactly
the named skills, still filtered through this same eligibility predicate —
an explicitly named but ineligible skill is reported (why: already shipped
/ already in flight / unconfigured / blocked by an unshipped hard
dependency), never silently dropped. A `--for` name that is not in v1's
declared set at all is reported as ineligible — "not in v1's fan-out set" —
and is likewise never fanned out.

**Exit 2.** When `lib.validate_settings` raises `GateError`, the snippet
catches it, writes the error to stderr, and exits 2: surface stderr verbatim
and stop — settings are invalid or acs is not initialized here (the same
contract `ship/SKILL.md`'s Start step uses).

**Checkout root.** `fanout_batches` is given `lib.checkout_root(cwd)`, never
the raw `cwd`: `doc_set_present_on_disk` resolves each skill's sentinel file
relative to that root, so a run started from a repo subdirectory (or from a
leg's own worktree on resume) would otherwise read an already-shipped doc set
as absent. This is the same resolution every gate uses —
`_require_architecture_doc_set` reads `ctx["checkout_root"]`
(`acs_lib.py:2354`), which `build_context` fills with `checkout_root(cwd)`
(`acs_lib.py:2139`).

**`--for` mechanism.** `lib.parse_fanout_for_arg($ARGUMENTS)` splits the
request into `requested` (names inside `DOC_BOOTSTRAP_FANOUT_V1`, which is
what `fanout_batches` is called with) and `rejected` (every name outside it).
Report EVERY rejected name explicitly, with the reason **not in v1's fan-out
set**, and never fan it out — a rejected name is never silently dropped and
never silently no-ops. With no `--for` flag, `requested` is `None` and
`fanout_batches` applies the declared v1 default.

**Bare `--for`.** `--for` given with no names at all selects nothing
(`requested == []`, `rejected == []`): report that `--for` requires at least
one skill name, and stop.

If the eligible batch is empty: report why, per candidate, and stop —
nothing to fan out.

## Worktrees — one per leg, created before that leg's Start

For every skill in this pass's eligible batch, create one git worktree
outside the consumer repo (`docs/requirements/functional/workspace-and-state.md`'s
worktree-per-unit-of-work convention), with a **generic, skill-scoped**
directory name — never ticket-id-named, because the delivery ticket id does
not exist yet (`skill-start.py --allocate` mints it only once that leg's
Start actually runs):

```bash
git worktree add --detach <path> <default-branch>
```

The `--detach` form is required, not cosmetic: the session checkout already
has `<default-branch>` checked out, so a plain (non-detached) `git worktree
add <path> <default-branch>` fails outright — `fatal: '<default-branch>' is
already used by worktree at …` — because git refuses to check the same
branch out into two worktrees at once. `--detach` sidesteps that by leaving
the new worktree in a detached-HEAD state at `<default-branch>`'s tip, which
still leaves `git status --porcelain` empty (a clean tree, true by
construction since the worktree was just freshly created) and still lets
that leg's own Branch step (below) run `git checkout -b <rendered branch>`
from it once that leg's ticket id exists.

**D3.2(ii) — where `skill-start.py` runs.** Every step through this leg's
own Start — including `skill-start.py --skill <skill> --allocate` — runs
from the **session checkout** (`cwd` unchanged), never from the worktree.
Running `skill-start.py` from the worktree instead would resolve a
different `checkout_id` than the one the pre-hook's `PreToolUse(Skill)`
envelope already used for its session marker, rejecting that marker on
mismatch and degrading the run to zeroed tokens / `cost_usd: None` /
`cost_basis: "unavailable"` on **both** legs — this design deliberately
avoids that by keeping `skill-start.py` in the session checkout, at the
cost of the session pointer/marker/cost-cursor becoming genuinely shared
between the two legs (display-level only — every downstream consumer is
still given the ticket id explicitly).

**When the worktree is actually entered.** Once that leg's own Start has
minted its ticket id, the coordinator enters that leg's own worktree and
runs that leg's own Delivery **step 1 (Branch)** there — the clean-tree
precondition is already satisfied (`git status --porcelain` empty, true by
construction from the freshly created worktree above), then `git checkout -b
<rendered branch>` — **before the Execute phase**, exactly as
`create-quality/SKILL.md`'s own Branch step requires ("before the first
executor writes: require a clean working tree" — cited, never restated).
The worktree is therefore entered at that leg's own Branch step, **not
merely once Delivery begins**: every subsequent write for that leg — both
executors' doc writes (`## Reflection loop` below) and Delivery steps 2-4
(commit, push, `gh pr create`) — happens inside that leg's worktree on that
branch; each executor's `<task>` carries that leg's worktree-absolute
output paths, so its writes cannot land in the session checkout.

## Starts — sequential, real Skill-tool calls

Invoke each eligible skill's Start **sequentially** — never concurrently,
and never from inside a spawned subagent (no acs subagent may hold both the
Agent and Skill tools; decomposition stays exclusively the coordinator's
job):

```
Skill(acs:create-quality)
Skill(acs:create-operations)
```

Each of these is a genuine Skill-tool call, so the real `PreToolUse(Skill)`
hook fires per leg exactly as it would standalone — the same precedent
`/acs:ship` already relies on: "/acs:ship is NOT a hooked skill, but every
step it invokes IS gated by pre/post hooks" (`ship/SKILL.md`, Ground
rules). You never bypass, simulate, or duplicate either leg's hook — each
leg's own `pre-create-quality.py` / `pre-create-operations.py` gate runs
for real, and each leg's own `post-create-quality.py` /
`post-create-operations.py` finalizes it for real.

### Fail-fast carve-out (D6-B) — narrowly scoped to the one shared gate

Both `gate_create_quality` and `gate_create_operations` check exactly one
shared precondition, `_require_architecture_doc_set` (the architecture doc set
— `hld/tech-stack.md` — must exist). Because the two Starts run sequentially,
if leg A's Start fails on that **shared** gate, you already know leg B's
identical gate would fail too — before spending a second Skill-tool call and a
second delivery ticket on a guaranteed-identical failure. In that case: **fail
fast** — stop immediately after the first gate failure, report ONE finding
naming the shared cause (architecture doc set missing), mark **both** legs
`not_attempted` (never `failed` — neither leg's Start actually ran), and do not
invoke the second leg's Skill call at all. Remove both legs' worktrees (`git
worktree remove <path>`) before reporting — they were created before either
Start ran, so leaving them in place would make the documented retry's `git
worktree add --detach <path> <default-branch>` fail on an already-occupied
path.

This carve-out is **scoped exclusively** to `_require_architecture_doc_set`.
Every other failure — a leg-specific hook block, a lock held by another
session, or a verifier cap reached at iteration 3 — falls straight through
to ordinary per-leg isolation, never this carve-out.

If a leg's own Start (`skill-start.py --skill <skill> --allocate`) exits
non-zero for any other reason, STOP and surface its stderr verbatim to the
user — never improvise a substitute; this is ordinary per-leg isolation, not
a variant of the carve-out above. One specific case: on a fresh/unreconciled
workspace partition, `--allocate` refuses with exit 2 and a ranked
local-evidence reconciliation proposal (`allocate_ticket_id`'s fail-closed
gate, MAR-402) instead of minting that leg's delivery ticket id. Relay that
stderr verbatim, obtain the confirmed start number from the user — never
invent it — and re-run that leg's Start with `--seed-next <n>` added.
Because both legs allocate from the same `(repo_id, prefix)` partition,
ADR-0087 records that every leg refuses simultaneously against an
unreconciled partition, and the first leg's successful `--seed-next`
reconciles it for every later leg, so the second leg's retried Start
proceeds normally without hitting the refusal again.

## Reflection loop — parallel phase batches, one coordinator

Once both legs have minted their own delivery ticket via their own Start
(`skill-start.py --skill <skill> --allocate`, run in the session checkout
per D3.2(ii) above), drive both legs' reflection loops together **from this
coordinator** by spawning each phase's existing planner/executor/verifier
agent files in parallel batches — reusing, **verbatim**, the mechanism
`/acs:code`'s coordinator already uses to run "several executors in
parallel" when their file maps are disjoint, and to spawn "the same agent
file, four times" for its multi-lens verify (`code/SKILL.md`) — this is
reuse of an existing, proven mechanism, never a new one:

1. **Plan** (once, before the loop) — spawn `acs:create-quality-planner` and
   `acs:create-operations-planner` in ONE message (both Agent-tool calls in
   the same coordinator turn). Each planner runs exactly the Plan step its
   own SKILL.md already documents — `create-quality/SKILL.md` `##
   Reflection loop` and `create-operations/SKILL.md` `## Reflection loop` —
   cited here, never restated, per the drift-mitigation requirement: a
   future change to either skill's own reflection-loop prose is a
   documented place to re-check this umbrella. Exactly one planner per leg
   across the whole run: however many execute→verify iterations a leg
   needs, its planner is never re-spawned (the same topology
   `create-quality/SKILL.md`'s own `## Reflection loop` already fixes for a
   standalone run). On iterations 2 and 3, a leg's verifier findings go
   straight into that same leg's own executor `<context>`, with no planner
   spawn in between and never into the sibling leg's executor.
2. **Execute** — after both planners return, spawn
   `acs:create-quality-executor` and `acs:create-operations-executor` in
   one message. Both executors write in the leg's own worktree **on the
   branch that leg's own Branch step already created** (`## Worktrees`
   above) — never the session checkout — to disjoint doc directories
   (`docs/quality/**` vs `docs/operations/**`); each executor's `<task>`
   carries that leg's worktree-absolute output paths. The disjoint-file-map
   precondition `/acs:code`'s own parallel-executor rule requires is
   satisfied by construction.
3. **Verify** — after both executors finish, spawn both verifiers,
   `acs:create-quality-verifier` and `acs:create-operations-verifier`, in
   one message.

Each leg's own iteration cap (max 3 execute→verify rounds), phase-artifact
paths (`<leg-partition>/phases/create-quality/iter-<n>-<phase>.xml` /
`<leg-partition>/phases/create-operations/iter-<n>-<phase>.xml`), and
Finish/result-document contract are **unchanged** — see
`create-quality/SKILL.md` `## Reflection loop` / `## Finish` and
`create-operations/SKILL.md` `## Reflection loop` / `## Finish`, cited
rather than restated here.

Validate EVERY message you send or receive, for BOTH legs, with the same
call every acs coordinator already uses:

```bash
echo "<xml>" | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate_xml.py" -
```

On an invalid message, re-request it once; if still invalid, fail **that
leg's** run with the validation error recorded in its own `errors` — never
the other leg's.

## Delivery — worktree per leg, two independent PRs

Once a leg's verifier returns zero findings, **continue** in that leg's
worktree (already entered at its own Branch step, `## Worktrees` above —
never the session checkout) with Delivery steps 2-4 (commit, push, `gh pr
create`) — exactly as `create-quality/SKILL.md` `## Delivery (branch,
commit, PR)` / `create-operations/SKILL.md` `## Delivery (branch, commit,
PR)` already specify, cited rather than restated. Each leg's own
`post-create-quality.py` / `post-create-operations.py`
finalizes it exactly as a standalone run would — its own
`pipeline-state.json`, its own `tickets-index.json` entry, its own
delivery ticket moved to `in_review`. The result is two independent
delivery tickets and two independent docs-only PRs (D3-B) — never one
shared branch, never a combined PR.

## Failure isolation (D6-B) — per leg, outside the shared-gate carve-out

Outside the shared-gate carve-out above, **every** failure is isolated to
its own leg — a leg-specific hook block, a verifier cap reached at
iteration 3, a lock held by another session — falls straight through to
ordinary per-leg isolation, never the carve-out. The failing leg's run
status, ticket, partition, and lock are its own: the OTHER leg's run, PR,
and ledger are never touched by it — no shared failure state between them
(AC-3). Report each leg's outcome independently, each with its own resume
command (see Resume below).

## Resume

There is **no fan-out batch ledger of its own** (D5-A) — each leg's own
`pipeline-state.json`, written under `flow: "product"` with its own step
key (`create-quality` or `create-operations`), is the complete resume
record for that leg. `/acs:ship` never drives these: its `flow: "product"`
refusal ("If `pipeline-state.json` has `"flow": "product"` … /acs:ship does
not drive those … and stop", `ship/SKILL.md`) is **restated here, never
reversed** — unchanged by this ticket.

A leg that failed, was interrupted, or was handed off resumes **exactly**
like any standalone run of that skill — never a re-invocation of this
umbrella:

```
/acs:create-quality <ticket-id>
/acs:create-operations <ticket-id>
```

Re-running `/acs:create-docs` itself simply re-derives the eligible batch by
re-running the Start section's `fanout_batches` detection: a skill with an
open (non-`done`) delivery ticket, or an already-shipped doc set, is
excluded from a **new** batch — it is already accounted for, either
in flight (resume it directly, above) or done. This is the umbrella's whole
resume mechanism; it is deliberately not a ship-style ledger walk (Hard
constraint D: there is no single shared ledger a walk could read, because
each leg writes a *separate* `pipeline-state.json` in a *separate*
partition).

## Context pressure

Your own context carries both legs' phase bookkeeping — bounded by two
skills' worth of prose (five small doc files total), unlike `/acs:code`'s
much larger single-ticket context; no `/acs:ship`-style "Full-verify
pipeline boundary" stop is needed at this scale. If you do run low
mid-batch, flush per-leg state to that leg's own
`<leg-partition>/phases/<skill>/handoff-context.md` (mirroring
`create-quality/SKILL.md`'s Context pressure section) before compacting.

## Completion report (normative)

Every terminal outcome ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered per leg — the shared-gate
carve-out collapses to one combined line (`not_attempted`, both legs):

```markdown
## /acs:create-docs · <status>

- **Batch**: <eligible skills this pass, or "none — see reasons">
- **create-quality**: <ticket-id> — <status> — <PR url, or reason>
- **create-operations**: <ticket-id> — <status> — <PR url, or reason>
- **Findings**: <the shared-gate carve-out finding, or "none">
- **Next**: <per-leg resume command(s), if any leg did not complete>
```
