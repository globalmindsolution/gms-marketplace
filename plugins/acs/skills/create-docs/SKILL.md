---
name: create-docs
description: Bootstrap or maintain the product doc sets — quality, operations, principles, standards — as the only user-facing entry point for them: detect which requested sets are eligible this pass and fan them out in capped parallel instead of running them one after another, each leg keeping its own hooks, reflection cycle and gating unchanged and delivering its own docs-only PR on its own delivery ticket. Use for any of those doc sets, with `all` or a comma-separated list, instead of invoking /acs:create-quality, /acs:create-operations, /acs:create-principles or /acs:create-standards directly.
argument-hint: "[all | <set>[,<set>...]]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-docs — an unhooked umbrella, exactly
like `/acs:ship`, `/acs:test`, and `/acs:release`: you have no
planner/executor/verifier of your own, and you never write a doc file
yourself. You are also the **only user-facing command** for the four product
doc sets: `create-quality`, `create-operations`, `create-principles` and
`create-standards` are internal legs of this skill (an entry-point fold, not a
collapse — each keeps its own SKILL.md, agent trio, `pre-`/`post-` hooks, gate
and sentinel, and each stays Skill-invocable exactly as before). You detect
which requested doc sets are eligible for parallel fan-out this pass, run each
eligible leg's own Start **sequentially** as a genuine Skill-tool call (so
every existing hook fires exactly as it would standalone), and then drive the
running legs' reflection loops together from your own context by spawning each
phase's subagents in parallel batches, capped (`## Concurrency cap` below).

Ground rules, non-negotiable:

- Every fanned-out skill's own hooks (pre/post), reflection cycle
  (planner/executor/verifier), and gating fire unchanged. You add
  orchestration only — you never bypass, simulate, or duplicate a hook.
- You have no planner/executor/verifier of your own. Each fanned-out skill
  runs its OWN reflection cycle via its OWN existing agent files
  (`acs:create-quality-planner/-executor/-verifier`,
  `acs:create-operations-planner/-executor/-verifier`, and the matching
  `acs:create-principles-*` / `acs:create-standards-*` trios), which you spawn
  directly with the Agent tool — you never do a leg's work yourself.
- The eligible set is `acs_lib.DOC_BOOTSTRAP_FANOUT_V1`, today every one of
  the four doc-bootstrap legs. A fifth doc-bootstrap skill becoming
  fan-out-eligible later is a data change, not a code change: it must be
  added to ALL FOUR of `acs_lib.DOC_BOOTSTRAP_DEPENDENCIES`,
  `acs_lib.DOC_BOOTSTRAP_FANOUT_V1`, `acs_lib.DOC_BOOTSTRAP_SETTINGS_KEY`,
  and `acs_lib.DOC_BOOTSTRAP_SENTINEL`, never an edit to this skill.
- This is not epic-child fan-out (`ship/SKILL.md`'s "Epic fan-out" section,
  unchanged) — that mechanism parallelizes *tickets* sharing one design;
  this skill parallelizes independent *product-level doc-bootstrap skills*
  that share no ticket and no design step.

## Argument — `<set|all>`, positional and comma-separated

`/acs:create-docs <set>[,<set>...]` or `/acs:create-docs all`. A `<set>` is
`quality`, `operations`, `principles` or `standards`; the full skill name is
accepted for each, so `quality` and `create-quality` resolve to the same leg.
`all` selects every declared leg (`acs_lib.DOC_BOOTSTRAP_FANOUT_V1`) and must
be passed on its own — `all,quality` is refused, never guessed at. No
argument at all keeps the previous behaviour: the declared default set, now
four sets wide.

You never parse this yourself. `acs_lib.parse_doc_set_arg` (beside
`acs_lib.parse_fanout_for_arg`) is the declared parser and the Start snippet
below calls it: it returns `candidates` (canonical leg names, or `None` for
"no argument"), `rejected`, and `notices` — the exact one-line messages to
write to stderr, in order. A token that **names no doc set** is rejected and
refuses the WHOLE run (exit 2, with a notice naming every accepted spelling);
the recognized remainder is never quietly fanned out instead, and no rejected
name is ever silently dropped.

`--for <skill>[,<skill>...]` stays accepted for **one release**. It parses to
the same canonical names and adds exactly one deprecated-form note on stderr
saying the positional form is the spelling now — the same one-release
courtesy the `test` → `run-e2e-tests` alias gets. Bare `--for`, with no names,
selects nothing: report the notice and stop.

## Concurrency cap

Never launch all four legs at once: run **at most 2** legs concurrently. That
cap is the ship workflow's `max_parallel` default (`DEFAULT_MAX_PARALLEL` in
`acs_lib`), and this repo's `workflows/ship.yaml` — or its
`.acs/workflows/ship.yaml` override — wins when it declares its own value,
which the Start snippet resolves and prints as `max_parallel`.
Walk each batch `fanout_batches` returns in **slices of at most
`max_parallel`** legs, finishing one slice's legs before starting the next.
Everything below that says "this slice" means those at-most-`max_parallel`
legs; the batch order itself is never re-derived by you (Start section below).

## Start — eligibility detection

MANDATORY first action — resolve settings, the argument, and the eligible
batch:

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
request = lib.parse_doc_set_arg(args_text)
for note in request.notices:
    sys.stderr.write(note + "\n")
if request.rejected or request.candidates == []:
    sys.exit(2)
try:
    max_parallel = lib.resolve_workflow(root)["workflow"].get(
        "max_parallel", lib.DEFAULT_MAX_PARALLEL)
except lib.WorkflowError:
    max_parallel = lib.DEFAULT_MAX_PARALLEL
batches = lib.fanout_batches(settings, tickets_index, root, candidates=request.candidates)
print(json.dumps({"workspace": workspace, "repo_id": repo_id, "checkout_root": root,
                  "requested": request.candidates, "rejected": request.rejected,
                  "notices": request.notices, "max_parallel": max_parallel,
                  "batches": batches}, indent=2))
PY
```

`acs_lib.fanout_batches(settings, tickets_index, checkout_root)` is the
**declared, not inferred** eligibility predicate (AC-5): each doc-bootstrap
skill's dependency edges live in `acs_lib.DOC_BOOTSTRAP_DEPENDENCIES`
(`{"hard": [...], "soft": [...]}` per skill) — never a prose guess. With no
`candidates` argument, `fanout_batches` defaults to the declared gate,
`acs_lib.DOC_BOOTSTRAP_FANOUT_V1` — the fan-out set is that constant, a
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
with each other. That is why `create-principles` lands in an earlier batch
than `create-standards` on the default set: the split comes from that
declared edge through `fanout_batches`, never from an order written down
here — do not reorder, re-derive or hard-code the batches you are handed.

No arguments: fan out whatever `fanout_batches` returns for the declared
`DOC_BOOTSTRAP_FANOUT_V1` set. `<set>[,<set>...]` or `all` (`## Argument`
above): fan out exactly the named sets, still filtered through this same
eligibility predicate — a named but ineligible set is reported (why: already
shipped / already in flight / unconfigured / blocked by an unshipped hard
dependency), never silently dropped.

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
(`acs_lib/gates.py`), which `build_context` (same module) fills with
`checkout_root(cwd)` (`acs_lib/repo.py`).

**Argument mechanism.** `lib.parse_doc_set_arg($ARGUMENTS)` splits the request
into `candidates` (canonical leg names, which is what `fanout_batches` is
called with), `rejected` (every token that **names no doc set**) and
`notices`. Write every notice to stderr in order. Report EVERY rejected name
explicitly, with the reason the notice gives — it names each unrecognized
token and every accepted spelling — and refuse the whole run (exit 2): a
rejected name is never silently dropped, never silently no-ops, and never
leaves the recognized remainder fanning out behind it. With no argument at
all, `candidates` is `None` and `fanout_batches` applies the declared
default. `lib.parse_fanout_for_arg` is the legacy `--for` half of the same
parser and is what emits the deprecated-form note; you call
`parse_doc_set_arg` only.

**Bare `--for`.** `--for` given with no names at all selects nothing
(`candidates == []`, `rejected == []`): report its notices — the deprecated-
form note plus "requires at least one doc set name" — and stop.

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
Skill(acs:create-principles)
Skill(acs:create-standards)
```

Only the legs in the current slice (`## Concurrency cap`), in the order
`fanout_batches` handed them to you — the four lines above are the declared
order, not an instruction to start all four.

Each of these is a genuine Skill-tool call, so the real `PreToolUse(Skill)`
hook fires per leg exactly as it would standalone — the same precedent
`/acs:ship` already relies on: "/acs:ship is NOT a hooked skill, but every
step it invokes IS gated by pre/post hooks" (`ship/SKILL.md`, Ground
rules). You never bypass, simulate, or duplicate any leg's hook — each
leg's own `pre-create-<set>.py` gate runs for real, and each leg's own
`post-create-<set>.py` finalizes it for real.

### Fail-fast carve-out (D6-B) — narrowly scoped to the one shared gate

Every doc leg's gate — `gate_create_quality`, `gate_create_operations`,
`gate_create_principles`, `gate_create_standards`
(`acs_lib.ARCHITECTURE_DEPENDENT_SKILLS`) — checks exactly one shared
precondition, `_require_architecture_doc_set` (the architecture doc set
— `hld/tech-stack.md` — must exist). Because the Starts run sequentially,
if the first leg's Start fails on that **shared** gate, you already know
every remaining leg's identical gate would fail too — before spending
another Skill-tool call and another delivery ticket on a
guaranteed-identical failure. In that case: **fail
fast** — stop immediately after the first gate failure, report ONE finding
naming the shared cause (architecture doc set missing), mark **every** leg in
this pass `not_attempted` (never `failed` — no leg's Start actually ran), and
do not invoke any remaining leg's Skill call at all. Remove every created
worktree (`git
worktree remove <path>`) before reporting — they were created before any
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
Because every leg allocates from the same `(repo_id, prefix)` partition, the
next leg's Start would hit the identical refusal — but Starts run
sequentially (this section), and you stopped at the first leg's refusal, so
no later leg's Start has run yet. Once that leg's `--seed-next <n>` succeeds,
it reconciles the partition, so the remaining legs' Starts then proceed
normally on their own first invocation — there is nothing to retry, since
they never ran. See
ADR-0087 for the reconciliation gate itself; its "simultaneously" framing
describes a fan-out that starts several `--allocate` legs at once, which
this skill does not do.

## Reflection loop — parallel phase batches, one coordinator

Once this slice's legs have minted their own delivery ticket via their own
Start (`skill-start.py --skill <skill> --allocate`, run in the session
checkout per D3.2(ii) above), drive the slice's reflection loops together
**from this coordinator** by spawning each phase's existing
planner/executor/verifier agent files in parallel batches — reusing,
**verbatim**, the mechanism `/acs:code`'s coordinator already uses to run
"several executors in parallel" when their file maps are disjoint, and to
spawn "the same agent file, four times" for its multi-lens verify
(`code/SKILL.md`) — this is reuse of an existing, proven mechanism, never a
new one:

1. **Plan** (once, before the loop) — spawn this slice's planners
   (`acs:create-quality-planner`, `acs:create-operations-planner`,
   `acs:create-principles-planner`, `acs:create-standards-planner` — the
   slice's, at most `max_parallel`) in ONE message (all its Agent-tool calls
   in the same coordinator turn). Each planner runs exactly the Plan step its
   own SKILL.md already documents — `create-<set>/SKILL.md` `##
   Reflection loop` —
   cited here, never restated, per the drift-mitigation requirement: a
   future change to a leg's own reflection-loop prose is a
   documented place to re-check this umbrella. Exactly one planner per leg
   across the whole run: however many execute→verify iterations a leg
   needs, its planner is never re-spawned (the same topology
   `create-quality/SKILL.md`'s own `## Reflection loop` already fixes for a
   standalone run). On iterations 2 and 3, a leg's verifier findings go
   straight into that same leg's own executor `<context>`, with no planner
   spawn in between and never into a sibling leg's executor.
2. **Execute** — after the slice's planners return, spawn each of the
   slice's executors (`acs:create-<set>-executor`, e.g.
   `acs:create-quality-executor`) in
   one message. Every executor writes in its own leg's worktree **on the
   branch that leg's own Branch step already created** (`## Worktrees`
   above) — never the session checkout — to disjoint doc directories
   (`docs/quality/**` vs `docs/operations/**` vs `docs/principles/**` vs
   `docs/standards/**`, each leg's own configured path); each executor's
   `<task>` carries that leg's worktree-absolute output paths. The
   disjoint-file-map precondition `/acs:code`'s own parallel-executor rule
   requires is satisfied by construction.
3. **Verify** — after the slice's executors finish, spawn each of the
   slice's verifiers (`acs:create-<set>-verifier`, e.g.
   `acs:create-quality-verifier`), in one message.

Each leg's own iteration cap (max 3 execute→verify rounds), phase-artifact
paths (`<leg-partition>/phases/<skill>/iter-<n>-<phase>.xml`, e.g.
`<leg-partition>/phases/create-quality/iter-<n>-<phase>.xml`), and
Finish/result-document contract are **unchanged** — see each leg's own
`create-<set>/SKILL.md` `## Reflection loop` / `## Finish`, cited
rather than restated here.

Validate EVERY message you send or receive, for EVERY leg, with the same
call every acs coordinator already uses:

```bash
echo "<xml>" | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate_xml.py" -
```

On an invalid message, re-request it once; if still invalid, fail **that
leg's** run with the validation error recorded in its own `errors` — never
another leg's.

## Delivery — worktree per leg, one independent PR each

Once a leg's verifier returns zero findings, **continue** in that leg's
worktree (already entered at its own Branch step, `## Worktrees` above —
never the session checkout) with Delivery steps 2-4 (commit, push, `gh pr
create`) — exactly as that leg's own `create-<set>/SKILL.md` `## Delivery
(branch, commit, PR)` already specifies, cited rather than restated. Each
leg's own `post-create-<set>.py`
finalizes it exactly as a standalone run would — its own
`pipeline-state.json`, its own `tickets-index.json` entry, its own
delivery ticket moved to `in_review`. The result is one independent
delivery ticket and one independent docs-only PR **per leg** (D3-B) — never
one shared branch, never a combined PR.

## Failure isolation (D6-B) — per leg, outside the shared-gate carve-out

Outside the shared-gate carve-out above, **every** failure is isolated to
its own leg — a leg-specific hook block, a verifier cap reached at
iteration 3, a lock held by another session — falls straight through to
ordinary per-leg isolation, never the carve-out. The failing leg's run
status, ticket, partition, and lock are its own: every OTHER leg's run, PR,
and ledger are never touched by it — no shared failure state between them
(AC-3). Report each leg's outcome independently, each with its own resume
command (see Resume below).

## Resume

There is **no fan-out batch ledger of its own** (D5-A) — each leg's own
`pipeline-state.json`, written under `flow: "product"` with its own step
key (`create-quality`, `create-operations`, `create-principles` or
`create-standards`), is the complete resume
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
/acs:create-principles <ticket-id>
/acs:create-standards <ticket-id>
```

These are the legs' own internal entry points, unchanged by the fold — a
leg keeps its SKILL.md, its hooks and its gate precisely so this resume
path (and this umbrella's Skill-tool calls) keep working.

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

Your own context carries the slice's phase bookkeeping — bounded by
`max_parallel` (2 by default) skills' worth of prose, which is why the cap
exists, unlike `/acs:code`'s
much larger single-ticket context; no `/acs:ship`-style "Full-verify
pipeline boundary" stop is needed at this scale. If you do run low
mid-batch, flush per-leg state to that leg's own
`<leg-partition>/phases/<skill>/handoff-context.md` (mirroring
`create-quality/SKILL.md`'s Context pressure section) before compacting.

## Completion report (normative)

Every terminal outcome ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered per leg — one line for each leg
this pass attempted; the shared-gate carve-out collapses to one combined line
(`not_attempted`, every leg):

```markdown
## /acs:create-docs · <status>

- **Requested**: <the sets you were asked for, or "default (all declared)">
- **Batch**: <eligible skills this pass, in slices of <max_parallel>, or "none — see reasons">
- **create-<set>**: <ticket-id> — <status> — <PR url, or reason>
- **Findings**: <the shared-gate carve-out finding, or "none">
- **Next**: <per-leg resume command(s), if any leg did not complete>
```
