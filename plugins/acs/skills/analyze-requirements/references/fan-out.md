# /acs:analyze-requirements — fan-out, messages and spawning

Open this before you spawn the first subagent of a run — the `survey`
action's lanes — and keep to it for every `synthesize`, `draft` and
`review` action after: how many instances run in one message, how the
survey and the judge are sliced, what each task and result carries, and how
an agent is spawned.

**Where the cross-references below point.** "Stage 1", "Stage 2" and
"Stage 3" are SKILL.md's sections.

## Passes, roles and the cap

**Every analyst task names its pass** in
`<constraint name="pass">requirements|synthesis|draft</constraint>` — the
`pass` field of the action. No third role plans the analysis (ADR-0092: when
the deliverable is the analysis, a plan for it is a second copy of the work):
the survey records what the requirements ask and touch in the authoring notes,
you settle its questions with the user, the draft pass authors the analysis
from both, and the impact reviewer re-derives the impact map from the
repository and judges the result fresh. The cap is a fixed **3**
on every run — `/acs:analyze-requirements` has no path-driven verify depth —
and the controller counts it: one iteration is one draft → review cycle, not
a lane.

## Parallelism — survey lanes and judge slices

Every fan-out is yours: spawn the N instances in ONE message (all foreground,
in the same message), wait for all of them, and only then call the `record`
verb. At most `settings.parallel.max_agents` (default 4) instances run per
message; beyond that, run the rest in waves of that size.

**Writer — one analyst, never sliced.** The analysis folder is one document
in several files: the README's verdict, criteria and contexts table summarize
every context file, and the context files cross-link rather than repeat each
other, so splitting the writer would only move that integration work into a
second pass. One analyst writes the whole folder on every iteration — and with
one writer there is no integration pass to run. The per-area work is already
done by the survey lanes. What fans out is the survey (Stage 1) and the judge
(Stage 3).

**Survey lanes.** Declare the code areas ONCE, with `acs.py analysis plan`,
by this rule: when the requirements' candidate impact spans **two or more disjoint
top-level areas** of the repo (top-level packages, services or apps: the
directories the architecture set, or failing that the repo root, names as
separate components), name each area by its directory basename (`api`, `web`,
`billing`); an area is a set of top-level directories and no directory belongs
to two areas, so no two slices survey the same path. A ticket inside one area
declares none, and gets one impact lane over the whole repository. The
analyst's requirements lane always runs beside them, so every survey has at
least two lanes and is always reconciled by a synthesis pass.

Each impact lane's task is `<task skill="analyze-requirements"
phase="impact-analyst" slice="<area>" …>` carrying
`<constraint name="survey_area"><the area's top-level paths></constraint>`
(the whole repository for the `repo` lane); it writes ONLY its
`iter-1/authoring-<area>.md` and `iter-1/impact-analyst-<area>.json`. The
requirements lane is `<task skill="analyze-requirements" phase="analyst"
slice="requirements" …>` with `<constraint name="pass">requirements</constraint>`.
`record-survey` joins every lane's notes into `iter-1/authoring.md`;
`record-synthesis` joins the synthesis last. Every lane's questions reach the
user in ONE grouped clarification-ledger ask (Stage 2), never one ask per lane.

**Judge slices.** The impact reviewer has seven check dimensions, so it
always runs as three slices, each a fresh instance of
`acs:analyze-requirements-impact-reviewer` whose task carries `slice="<id>"`
and `<constraint name="dimensions">` naming the dimension numbers it owns —
exactly the `slices` the `review` action prints:

| Slice | Dimensions | Owns the run of |
|---|---|---|
| `surface` | 2 `completeness`, 3 `api-surface` | the re-derivation of the impact surface from the repository, and the questions/ticket coverage check |
| `form` | 4 `front-matter`, 5 `structure`, 6 `scope` | `front_matter_check.py` and `structure_lint.py` on every file, and the folder's names and links |
| `evidence` | 1 `grounding`, 7 `authoring-conformance` | re-opening every citation in the notes and the draft |

Grounding policing applies in every slice. Each writes
`iter-<n>/impact-reviewer-<slice>.md`; `record-review` joins them, in the
table's order, into `iter-<n>/impact-reviewer.md`, drops exact duplicates
(same dimension, file and text) under a `## De-duplicated findings` section,
and derives the verdict: the iteration passes only if EVERY slice returned
`status="completed"` with zero blocking findings — never "pass with a missing
slice". A failed iteration's blocking findings are the next `draft` action's
`findings`; a set identical to the previous iteration's ends the run
`stalled` instead of spending another draft pass.

## Messaging rules (`the SubagentStop hook's message check`)

- Send each subagent one `<task skill="analyze-requirements"
  phase="analyst|impact-analyst|impact-reviewer" ticket-id="<id>"
  iteration="n">` — the `phase` is the role; `ticket-id` only when the run has
  a ticket — carrying `<objective>`, `<inputs>` (file refs) and
  `<constraints>`. The subagent returns a
  `<result>` with the same `phase` as its final content. A sliced instance's
  task and result also carry `slice="<id>"` (the action's `slice`); the draft
  pass omits it.
- Every phase's `<constraints>` carry `required_sections` (the README's six
  headings and a context file's five, `references/analysis-templates.md`) and
  `<constraint name="audience_style_profile">implementers (evidence
  + impact narrative)</constraint>`; every analyst task also carries
  `<constraint name="pass">`.
- The SubagentStop hook checks each returned `<result>`'s `skill=`, `phase=`
  and `iteration=` (and `slice=` when sliced) and snapshots it to the
  action's `snapshot` path — `steps/analyze-requirements/iter-<n>/<phase>-message.xml`,
  or `iter-<n>/<phase>-<slice>-message.xml` for a slice. The controller reads
  only those snapshots; if one is missing (a host that does not fire the
  hook), write the `<task>` and `<result>` there yourself. Never write a
  message over an agent's own report.
- Spawn subagents with the Agent tool: `subagent_type:
  "acs:analyze-requirements-analyst"`, `"acs:analyze-requirements-impact-analyst"`
  and `"acs:analyze-requirements-impact-reviewer"` — the action's `agent` —
  falling back to the un-namespaced name only if the runtime rejects the
  namespaced one. Spawn each role under the name in
  `context.agents.<role>` — the plugin's `acs:analyze-requirements-<role>`, or the
  generated `acs-analyze-requirements-<role>` copy `acs step start` wrote where
  `settings.models` sets a model or effort for it. Model and effort travel with
  that agent, so pass none of your own: the analyst's, impact analysts'
  and impact reviewer's model and effort come from
  `settings.models.analyze-requirements.<role>` (inheriting when unset). If the runtime rejects the agent, FAIL
  the run with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.
