# 0091 — The design phase narrows by an entry-point fold, not a skill collapse: a registry `internal` map, two unhooked umbrellas, and an auto-detected project mode

**Status**: Accepted · **Date**: 2026-09-12

## Context

The design phase had grown to twelve user-facing commands, six of which a
consumer could not order correctly without reading three ADRs. Four of them
bootstrap a product doc set — `/acs:create-quality`, `/acs:create-operations`,
`/acs:create-principles`, `/acs:create-standards` — and two scaffold a
repository, split by a property of the repo rather than of the user's intent:
`/acs:create-project` is greenfield-only and refuses an existing codebase,
`/acs:standardize-project` is its brownfield counterpart. The surface asked the
user to answer questions acs already had the evidence to answer: *which of the
four doc sets are eligible right now?* and *is this repo greenfield?*

Three earlier decisions each solved part of this and stopped at the same
boundary:

- **ADR-0011** established *one skill per doc set*, deliberately refusing to
  overload `/acs:create-architecture` with extra sets. That rule is still
  right, and it is about **production** — which skill writes which directory.
  Its premise was that one skill per set also means one *command* per set.
- **ADR-0083** dropped the per-iteration planner re-spawn across the five
  bootstrap-doc skills, treating them as a family with one shared loop
  topology. It established that the four doc-set siblings behave alike, but
  left each of them separately invocable.
- **ADR-0085** built the first fold: `/acs:create-docs`, an unhooked umbrella
  that fans two of those skills out in parallel. It scoped itself explicitly to
  a **v1 pair** (`DOC_BOOTSTRAP_FANOUT_V1` = `create-quality`,
  `create-operations`) with the general N-way case reachable only through an
  explicit `candidates` argument, and it left the legs fully user-facing — the
  umbrella was an *additional* command, not a replacement for them.

So the surface still carried every skill, and `/acs:create-docs` made it
larger rather than smaller. The question this ADR settles is not how to run
these skills — 0011, 0083 and 0085 answered that — but **how many of them a
user should have to know about**.

Two constraints bound every option. First, `create-docs/SKILL.md` runs each
leg's own Start "sequentially as a genuine Skill-tool call (so every existing
hook fires exactly as it would standalone)" — the umbrella *depends* on each
leg remaining a real, independently-loadable skill. Second, each of the six
carries a registered `GATES` entry, a `pre-`/`post-` hook pair, a
planner/executor/verifier trio and a sentinel; all of that is load-bearing for
its own run and none of it is duplicated in an umbrella.

Options weighed:

- **Status quo plus better docs.** Cheapest, and it does not work: the
  README's Design table was the documentation, and it listed twelve commands
  because there were twelve commands.
- **A true collapse** — merge the four doc-set skills into one skill with a
  mode argument, and the two project skills into one, deleting the legs'
  SKILL.md files, agents and hooks. The smallest surface, and rejected: it
  deletes the mechanism `/acs:create-docs` is built on, forces one gate to
  express four different preconditions, merges four verifier contexts into one
  (against ADR-0004's verification-independence property), and re-opens
  ADR-0011's one-skill-per-set decision to buy a narrower menu.
- **An entry-point fold (chosen).** Declare which skills are user-facing and
  which are internal legs, and change nothing else.

## Decision

### 1. An entry-point fold, not a collapse — declared in the registry

`workflows/phases.yaml` gains a third top-level key, sibling to `phases` and
`aliases`, mapping each internal leg to the single entry point that owns it:

```yaml
internal:
  create-quality: create-docs
  create-operations: create-docs
  create-principles: create-docs
  create-standards: create-docs
  create-project: project
  standardize-project: project
```

**A leg keeps everything that makes it a skill.** Its SKILL.md, its agent
trio, its `pre-`/`post-` hook scripts, its registered `GATES` entry, its
settings key and its sentinel are untouched, and its entry point invokes it as
a genuine Skill-tool call, so all of it fires exactly as on a standalone run.
The fold changes exactly one thing: **who may invoke it.** A leg is not a
command a user runs, it carries `disable-model-invocation: true` (the
`install-hooks`/`update` precedent), and it appears in no phase list. Its own
`/acs:<leg> <ticket-id>` form survives for one purpose — resuming a leg that
failed, was interrupted or was handed off, which its entry point never does on
its behalf.

This is the load-bearing half of the decision, and it is a *mechanical*
constraint rather than a preference: deleting a leg's SKILL.md would break the
umbrella that invokes it.

**The registry's name set becomes phase lists + `aliases` keys + `internal`
keys, and "exactly once" is asserted across all three.** `load_phases()` gains
four refusals, each naming the line that caused it: an `internal` key with no
`skills/<dir>`; an `internal` value that is not a phase-listed skill; an
`internal` key that is also phase-listed or an `aliases` key; and an `internal`
value that is itself an `internal` key — **there is no leg of a leg**, so the
map stays one level deep and every leg resolves to a user-facing command in one
step.

**`phase_of` resolves a leg through its entry point.** `skill_legs()` and
`entry_point_of(skill)` are the new accessors, and `phase_of("create-quality")`
stays `"design"` (via `create-docs`). This is what keeps a leg's run inside a
phase for any consumer that groups by phase — `/acs:metrics` above all —
instead of falling outside the five groups the moment a skill leaves the phase
lists. It does not merge a leg into its entry point anywhere else: a leg still
runs as its own gated skill with its own delivery ticket, so the metrics
pipeline funnel still keys on `HOOKED_SKILLS` and still shows each leg as its
own row. `allowed_ship_skills()` is unaffected — no leg is ship-eligible.

**`/acs:create-docs` becomes the only user-facing command for the four doc
sets**, taking a positional, comma-separated `<set|all>` argument
(`quality`/`create-quality` both resolve). `DOC_BOOTSTRAP_FANOUT_V1` widens
from ADR-0085's v1 pair to all four legs — one constant edit, because the other
three doc-bootstrap constants already covered four — so 0085's N-way case is
now the default path and its `candidates` argument carries a *narrowing*
request instead of a widening one. Concurrency is **capped** rather than
unbounded: the declared batches are walked in slices of at most `max_parallel`
legs (default 2, the ship workflow's own knob). The batch split still comes
from `DOC_BOOTSTRAP_DEPENDENCIES` through `fanout_batches` — the declared soft
edge `create-standards` → `create-principles` is what keeps them out of one
batch — never from an order written into prose.

### 2. `/acs:project` decides its own mode from declared on-disk evidence

A new unhooked umbrella at `plugins/acs/skills/project/SKILL.md` — no agents,
no gate, no `skill-start.py`, no reflection loop, added to `UNHOOKED_SKILLS`:
the `create-docs` shape. It replaces the greenfield/brownfield question with an
answer, then dispatches to `create-project` or `standardize-project` as a
genuine Skill-tool call so that leg's hooks and gate fire unchanged.

**Mode detection is a declared, unit-tested helper, never skill prose** —
`acs_lib.project_mode(settings, checkout_root)`, following the `fanout_batches`
precedent exactly. It reads `PROJECT_MODE_SETTINGS_KEY` /
`PROJECT_MODE_SENTINEL` (ten packaging, build and tooling files:
`pyproject.toml`, `setup.py`, `package.json`, `go.mod`, `Cargo.toml`,
`pom.xml`, `build.gradle`, `build.gradle.kts`, `.pre-commit-config.yaml`,
`.coveragerc`) off disk through the same `_sentinel_present` primitive
`doc_set_present_on_disk` uses — no git scan, no heuristic, no prose inference
— and returns the chosen mode, the full evidence list, and a one-sentence
reason the skill states back to the user.

**The partial case is deterministic and deliberate: ANY single present row
means `standardize`.** Only a repo with no declared evidence at all is
`bootstrap`. That fails toward the additive, idempotent leg —
`standardize-project` only ever adds, and a second run over an
already-standardized repo finds nothing to do — whereas failing the other way
would point `create-project` at a repo its own greenfield scan refuses
outright.

## Consequences

**Positive.** The design phase presents seven commands instead of twelve, and
the two it removed most of were the two that asked the user to supply evidence
acs already had. The narrowing costs no verification independence and no gate
integrity, because **no gate, triad or agent file moved**: 59 agent files and
20 `GATES` entries before the fold, 59 and 20 after — the counts are the
evidence that this is a fold and not a collapse. ADR-0011's one-skill-per-set
decision, ADR-0083's shared loop topology and ADR-0085's fan-out mechanism all
stand unamended; this decision narrows only their shared premise that one skill
per job means one *command* per job. And the fold is now a reusable pattern
with a declared home: a future "these three skills are really one job" becomes
an `internal` entry plus an umbrella, with the refusals above keeping the map
honest.

**Accepted cost: a skill's name no longer tells you whether you can run it.**
Six of the 32 skills on disk are legs, and the only way to know is to read the
registry — which is why the `internal` map is data rather than prose, why
`disable-model-invocation: true` makes the runtime agree with it, and why the
README table renders legs as legs rather than as commands. A reader who learns
acs from a leg's SKILL.md alone will not discover its entry point from the
body; the frontmatter `description` carries that pointer.

**Accepted cost: the umbrella is a second place a leg's behaviour is
described.** `create-docs/SKILL.md` cites each leg's own `## Reflection loop`
rather than restating it, precisely so the two cannot drift, but the citation
is a convention a future edit can break. A change to a leg's own loop prose is
a documented place to re-check the umbrella.

**Accepted cost: resume is the one path where a leg's own command is still
correct**, which is a genuine wart — the surface says "never run this" and the
resume instructions say "run this". It is kept because the alternative is
teaching each umbrella to resume a leg's half-finished run, which means the
umbrella reading a leg's `pipeline-state.json` and reconstructing its
iteration state: the shared-ledger coupling ADR-0085's D5-A deliberately
refused.

**Known open item, recorded rather than fixed.** Eight skills now set
`disable-model-invocation: true` — the two user-action-only skills plus all six
legs — but `evals/acs/scenarios/s04_skill_triggers.py` still probes the six
legs by *description*, which by its own rule 2 can never route to a skill
carrying that flag. Those six probes are expected to miss on the next paid run
and need moving to the explicit-invocation + negative-routing pair the other
two carriers use. That reclassification changes the measured routing-coverage
claim the PRD and roadmap carry, so it is deliberately left to a fresh paid
measurement rather than done blind alongside the fold. Tracked in
`docs/quality/testing-strategy.md`'s Trigger bullet and in that scenario's own
docstring.

**Not a release.** The plugin is unreleased at this decision's landing
(`plugin.json` and `marketplace.json` at 0.4.9, the marketplace pinned to
`v0.4.9`), so the fold lands as source and is not reachable through the cached
skills until a version is cut.

## References

- **ADR-0011** — full-SDLC doc sets (quality, operations): one skill per doc
  set. Unamended; its production rule stands, its one-command-per-set premise
  is narrowed here.
- **ADR-0083** — the bootstrap-doc skills' execute → verify remediation loop.
  Unamended; the five skills it governs keep that topology exactly, four of
  them now as legs.
- **ADR-0085** — doc-bootstrap parallel fan-out. Unamended; its umbrella,
  phase-level interleave, worktree-per-leg delivery, declared eligibility and
  no-new-ledger decisions all stand. Its **v1 pair** scope (D-set) and its
  "legs stay user-facing" assumption are what this ADR narrows:
  `DOC_BOOTSTRAP_FANOUT_V1` is now all four legs, and the umbrella is their
  only user-facing command.
- **ADR-0004** — reflection trio with an independent verifier: the property the
  rejected true-collapse option would have cost.
- **ADR-0089** — pipeline order declared in `workflows/ship.yaml`; the registry
  this decision extends with the `internal` map.
