# The designer's passes — iteration 1 fan-out, the join, the draft

Read before tasking iteration 1.

Weighing the options and writing them down are one act — the decisions and
trade-offs the survey records are the draft's own sections — so one role does
both, in three passes on iteration 1: the **scope pass** surveys the
requirements, the HLD, the feature's LLD and the codebase and lists the major
decisions; the **option-research pass** weighs each major decision's options
in parallel, one designer per decision; the **draft pass** — a single
designer, because `tech-design.md` is ONE document and cannot be split into
disjoint files — authors the draft from the joined notes. The reviewer then
judges the result fresh, itself sliced by dimension.

## Fan-out rules (every sliced phase)

- **One message, then wait for all.** The parallel instances of a phase are
  the SAME agent spawned N times in ONE message — one Agent call per slice,
  each `run_in_background: false` — and you wait for every one of them
  before the join. Cap: at most `settings.parallel.max_agents` (default 4)
  instances per message; more slices than that run in waves of that size, and
  the next phase starts only after the last wave is joined.
- **Slice ids.** Each instance's task and result carry `slice="<id>"`
  (`<task skill="create-tech-design" phase="designer" slice="d1" …>`), so the
  SubagentStop snapshot lands at `iter-<n>/<role>-<id>-message.xml` and
  siblings never collide. A slice id is a short lowercase token (letters,
  digits, hyphens). A single, un-sliced instance omits `slice` and writes
  the un-suffixed file names.
- **The join is deterministic** — never merge prose by hand:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/create-tech-design/iter-1/authoring.md \
  <partition>/steps/create-tech-design/iter-1/authoring-scope.md \
  <partition>/steps/create-tech-design/iter-1/authoring-d1.md <…/authoring-d2.md> …
```

  It merges by `## ` heading — the first file's preamble, each H2 once in
  first-seen order, the bodies concatenated in input order, each prefixed by
  a `<!-- slice: <id> -->` line — writes `--out`, prints `{ok, out,
  sections, inputs}`, and fails on a missing input. The draft designer and
  the reviewer read the ONE joined file, each section once.

## Iteration 1

1. **Scope pass** — ONE designer, `slice="scope"`, writes no draft: the
   whole survey into `iter-1/authoring-scope.md` (every section of the
   notes — including the HLD views and the living LLD documents the change
   touches, each with the version `acs.py design check` printed), with each
   major decision given a short id `d1`, `d2`, … and its preliminary options,
   plus `iter-1/designer-scope.json`; it also runs the ADR-0012
   doc-consistency step.
2. **Option-research pass — parallel, when the scope notes list two or more
   major decisions.** One designer per major decision, `slice="<decision
   id>"`, all spawned in ONE message (at most `settings.parallel.max_agents` per wave), each task carrying
   `<constraint name="decision">` with that decision's id and one-line
   statement and the scope notes in `<inputs>`. The partition is by
   decision: a research slice researches ONLY its own decision — its
   candidate options (>=2 genuinely viable, how each works), their
   trade-offs against the NFR checklist and constraints, the code and doc
   evidence, and that decision's genuinely open points — and writes ONLY
   `iter-1/authoring-<id>.md` (sections `## Decisions & candidate options`,
   `## Open questions`, `## Risks`) and `iter-1/designer-<id>.json`; it never
   touches the draft or another decision's file, so the slices cannot
   overlap. With fewer than two major decisions there is nothing to split:
   skip this pass — the scope notes' options stand.
3. **Join** — `acs.py notes merge --out iter-1/authoring.md
   iter-1/authoring-scope.md iter-1/authoring-<id>.md …` (scope first, then
   the research slices in decision order; with no research pass, the scope
   file alone). The joined file is iteration 1's authoring notes.

Any pass may return `needs_input` with `<questions>` for genuinely open
points. Hold the scope pass's questions until the research pass has
finished, then resolve every pass's questions together in ONE grouped
interaction (User interaction) and give the draft designer the answers in
`<context>`.

4. **Draft pass** — ONE designer, un-sliced, with the joined
   `iter-1/authoring.md` in `<inputs>`, writes the draft at
   `steps/create-tech-design/tech-design.md` (a seeded re-design: revises it
   in place, below its front-matter block) and `iter-1/designer.json`. It is
   the single consumer of the research slices,
   so it MUST synthesize them, not just read their join: where two slices'
   notes (or the scope notes and a research slice) contradict each other —
   one option's cost or feasibility claimed differently, an NFR bound, a
   shared component described two ways — it records the resolution with its
   evidence under a `## Synthesis` heading in `iter-1/authoring-synthesis.md`,
   or returns `needs_input` with the contradiction as a question; never
   silently picks one. After the draft pass, redo the join with that file
   appended (`acs.py notes merge --out iter-1/authoring.md
   iter-1/authoring-scope.md iter-1/authoring-<id>.md …
   iter-1/authoring-synthesis.md`), so iteration 1's notes — the ones the
   reviewer judges against — carry the Synthesis. With no research
   pass there is nothing to synthesize and the file is not written. The
   draft pass writes no other authoring notes on iteration 1 — the joined
   notes are that iteration's notes. Then run `acs.py design init` on the
   draft (SKILL.md, Version front matter).

## Iterations 2-3

A single designer, un-sliced, revises the draft and writes that iteration's
full `iter-<n>/authoring.md` itself (with its Findings addressed section): the
draft is one document, so the write never fans out — and with one writer
there is no integration pass to run (it is skipped when only one writer
ran). If the draft designer returns `needs_input` with `<questions>`, resolve
them in User interaction and re-run the designer for the same iteration with
the answers in `<context>`.

Only the option-research pass runs designers in parallel, and only because
its slices own disjoint files (`iter-1/authoring-<id>.md`, one per decision).
Two designers never touch the draft in the same iteration. The reviewer runs
after ALL designers finish and judges the combined result.
