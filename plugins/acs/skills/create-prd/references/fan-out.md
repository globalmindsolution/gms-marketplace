# /acs:create-prd — spawning, messages and the fan-out

Open this before the first spawn of a run and keep to it for every phase
after: how an agent is spawned and waited on, how its messages are checked
and persisted, and the rules every sliced phase follows.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

All messages follow `the SubagentStop hook's message check`; the `phase=` of
every task and result is the role (`surveyor`, `author`, `reviewer`). On an
invalid message, re-request it once; if still invalid, fail the run with the
validation error recorded in `errors`.

Every phase output is persisted at the phase boundary, BEFORE the next phase
starts: the SubagentStop hook snapshots each returned message to
`steps/create-prd/iter-<n>/<role>-message.xml`; if that snapshot is missing (a
host that does not fire the hook), write the `<task>` and `<result>` there
yourself. The roles' own artifacts are the authoring notes
`iter-<n>/authoring.md` (Mode & evidence; PRD outline; Roadmap outline; Code
evidence; Answer fidelity; Roadmap milestones; Open questions; Risks; Reviewer
checklist — the surveyor writes iteration 1's, the author completes them and
carries them forward), `iter-1/surveyor.json`, `iter-<n>/author-hub.json` and
`iter-<n>/author-feature-<slug>.json` (the author is always sliced:
`author-slices.md`), each feature author's `features/<slug>/notes.md` and
`iter-<n>/reviewer.md`; every iteration's reviewer `<inputs>` name that
iteration's authoring notes. Decomposition is YOURS alone — subagents never
spawn subagents.

### Fan-out — slices, the join, the cap

Every fan-out in this skill is yours: you spawn N instances of the SAME agent
in ONE message (all foreground, all in the same Agent-tool batch), wait for
ALL of them, and join their outputs before the next phase starts. The rules
every sliced phase follows:

- **Slice id on the wire.** Each parallel instance's `<task>` carries
  `slice="<id>"` (`<task skill="create-prd" phase="reviewer" slice="delta" …>`)
  and its `<result>` echoes it, so the SubagentStop snapshot lands at
  `iter-<n>/<role>-<id>-message.xml` with no collision. An un-sliced instance
  omits `slice` exactly as before. A slice id is a short lowercase name
  (`api`, `web-app`, `delta`); the join derives each id from the part of the
  file name after the prefix all its inputs share, so ids may carry hyphens.
- **Slice plan first.** Before spawning, write (through `acs.py write`) the partition to
  `steps/create-prd/iter-<n>/<role>-slices.json` (`{"<id>": [<the paths or
  dimension numbers it owns>], …}`), so a resume knows which slices were
  planned. The author's plan lists the feature wave only — written once the
  `hub` has returned (`author-slices.md`); the `hub` is evidenced by its own
  report.
- **Per-slice files.** A surveyor slice writes `iter-1/authoring-<id>.md` and
  `iter-1/surveyor-<id>.json`; an author slice writes `iter-<n>/author-<id>.json`
  (a feature author also its `features/<slug>/notes.md`); a reviewer slice
  writes `iter-<n>/reviewer-<id>.md`.
- **The join is deterministic, never prose-merging by you.** One command joins
  the slice files by `## ` heading (first file's preamble; each H2 once, in
  first-seen order; bodies concatenated in input order, each prefixed by a
  `<!-- slice: <id> -->` line) into the ONE file every downstream reader and
  checker reads:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
    --out <partition>/steps/create-prd/iter-<n>/<joined file> \
    <partition>/steps/create-prd/iter-<n>/<slice file 1> <…slice file 2> …
  ```

  It prints `{ok, out, sections, inputs}` and refuses when a slice file is
  missing — a missing slice is a failed slice, never a smaller join.
- **Cap.** At most `settings.parallel.max_agents` (default 4) instances per
  message; beyond the cap, run the slices in waves of that size (each wave one
  message) and join once after the last wave.
