# Skill rubric

How good is a skill? Every other document in this set, and every document in
[acs-evals](https://github.com/globalmindsolution/acs-evals), deliberately
refuses to answer that. `acs-evals/docs/RUBRIC.md` ranks *the consequence of a
case failing*, and says so outright: "whether acs should behave that way in the
first place is a design judgement this dataset deliberately does not make."
`EVALUATION-PROCESS.md` opens by disclaiming the same question. Both are right
to: a golden dataset that graded its own subject would have nothing left to
compare against.

That leaves a real gap, because the eval report is what we read before a
release in order to *improve* skills. A green run tells us nothing moved. It
does not tell us which skill to work on next. This rubric does.

It grades a **skill**, not a case, and it answers one question:

> **If a user reaches for this skill, does it do the job — and can we show
> that, rather than assume it?**

## The six dimensions

Each dimension has evidence that already exists in this repo. A dimension with
no evidence is **not** a pass — see "Unmeasured is not a pass" below.

### 1. Routing — does the request reach it?

The `description` frontmatter is the whole interface for a model-invocable
skill. The dimension asks whether it is *discriminating*, not whether it is
well written: a description that wins its own probe but also wins its
neighbour's is worse than a plain one that wins only its own.

- **Evidence**: the skill's probe in `evals/acs/scenarios/s04_skill_triggers.py`
  and `acs-evals/dataset/routing.json`, measured over 5 runs.
- **Blocks** when reliability is below 100%. Routing is an absolute floor —
  `acs-evals/docs/PERFORMANCE.md` already treats it as one, and a skill that
  routes 4 times in 5 fails one user in five.
- **Reports, never blocks**: time-to-route. The median across description
  probes is ~3.0s; `ship` at 6.5s and `create-requirements` at 5.2s are slower
  but correct. Slow usually means the description makes the model deliberate —
  worth a look, never a release blocker, and never worth an unmeasured edit.
- **For a user-only skill** (`disable-model-invocation: true`) the dimension
  inverts: the explicit command must route AND the bare description must NOT.
  A user-only skill with no negative probe is unmeasured on the half that
  matters, because the no-auto-invoke guarantee is the one the docs make.

### 2. Gate — does it refuse what it must refuse?

- **Evidence**: the skill's `GATE-*` cases, and its entry in `acs_lib.GATES`.
- **Blocks** when a gate opens that should have stayed shut, or a fail-closed
  path fails open. This is the one dimension where `acs-evals`' `critical`
  severity maps straight across.
- An unhooked skill (`ship`, `create-docs`, `project`, `release`, …) has no
  gate **by construction**, which is n/a, not a gap. Judge it on the gates of
  the legs it drives.

### 3. Contract — does it produce what it promises?

The skill's own `## Finish` block names a result document and its `states`
keys. This dimension asks whether those artifacts actually appear, with those
keys, and whether the derived ones are derived rather than trusted from the
coordinator's prose.

- **Evidence**: a layer-6 behavioural scenario asserting on the workspace
  artifacts.
- **Blocks** when the skill claims a key it does not write, or writes one the
  post-hook is supposed to derive.
- **Today this is the weakest dimension in the set**: 3 of 32 skills have any
  artifact-level assertion (`create-ticket`, `code`, `create-pr`). Every other
  skill is unmeasured here, which is exactly what PRD **G31** tracks.

### 4. Structure — is the document itself conformant?

- **Evidence**: the `SKILL-*` case in `acs-evals/dataset/cases/10-skills.json`
  (frontmatter: `name`, a non-empty `description`, the invocation flag), and
  `structure_lint.py` against the skill's own declared `required_sections`
  (ADR 0056 — the list the executor is told to write IS the list the verifier
  checks, so there is no second copy to drift).
- **Blocks** when a required section is missing or the frontmatter is
  malformed. Cheap to check, and it is the failure that makes every other
  dimension unreadable.

### 5. Recovery — what happens when a run dies?

Long skills get interrupted. The dimension asks whether the next session can
pick the work up, and whether the interrupted one let go of what it held.

- **Evidence**: `s03_resume_and_verify`, `session_end_safety_net`, and the
  skill's own Resume & reconcile section.
- **Blocks** when a resumed run trusts recorded state it has not re-verified,
  or when an abnormal end leaves a lock held. "Trust nothing that fails" is the
  standing rule in `code/SKILL.md`; a skill whose resume path merely reads the
  state file does not satisfy this dimension.
- A skill with no reconcile path because it cannot be interrupted mid-flight
  (a read-only dashboard) is n/a.

### 6. Prose — can a coordinator follow it without guessing?

The one dimension with no deterministic check, so it is judged, not measured —
and judged narrowly, on things that have a right answer:

- the `argument-hint` matches what the skill actually parses;
- every command it tells you to run exists at the path it gives;
- its examples use the placeholders it defines;
- audience-style (verdict dimension 13, ADR 0063) — a skill document is
  written for the coordinator executing it, not for a reader admiring it.

**Reports, never blocks.** Prose findings are real, but a release has never
been made worse by shipping a clumsy sentence, and treating them as blocking
is how a rubric gets ignored.

## Unmeasured is not a pass

The single most important rule here, and the one the codebase already commits
to elsewhere: the routing harness's `classify()` reports `unmeasured` and
counts it as **"a miss, never a pass"** when the stream carries no registration
list. Apply the same default to every dimension.

A skill with no probe is not a skill with good routing — it is a skill whose
routing nobody has looked at. Seven skills were in exactly that state until
recently, and the six closest-named ones in the whole set were among them.

So a dimension is one of:

| State | Meaning |
|---|---|
| **pass** | evidence exists and is green |
| **fail** | evidence exists and is red |
| **unmeasured** | no evidence — treated as fail for release purposes, and named as a coverage gap rather than a defect |
| **n/a** | the dimension cannot apply, by construction, with the reason stated |

`unmeasured` and `fail` both block, but they are fixed differently: a `fail`
needs the skill changed, an `unmeasured` needs a case written. Conflating them
is how "we have no test for that" turns into "that works."

## The verdict

Per skill, and deliberately **not a score**:

| Verdict | Condition |
|---|---|
| **Ready** | routing, gate, contract, structure and recovery all pass or n/a |
| **Thin** | all applicable dimensions pass, but one or more is `unmeasured` |
| **Blocked** | any applicable dimension fails |

`Thin` is the state most of this plugin's skills are in today, and naming it
separately is the point of the rubric: a thin skill is not a broken skill, and
it is not a finished one either.

There is no composite number, for the reason `acs-evals/docs/RUBRIC.md` gives
about its own levels: a percentage "invites shipping on a number", and one
skill that refuses to route is not offset by thirty-one that do.

## Using it before a release

1. Run the deterministic tier and the routing measurement. Both are described
   in `evals/README.md`; the routing half costs money, the rest does not.
2. Fill the matrix in
   [`testing-strategy.md`](testing-strategy.md) — it already carries a
   per-skill row per layer, and those layers map onto dimensions 1, 2, 3 and 4.
3. Work `Blocked` before `Thin`, and within `Thin`, close `contract` before
   `prose` — a skill nobody can show produces the right artifact is a worse
   risk than one that reads awkwardly.
4. An `unmeasured` dimension closed by writing a case is progress worth
   recording even when the case passes first time. It converts an assumption
   into evidence, which is the only thing that moves a skill from `Thin` to
   `Ready`.

## What this rubric does not do

It does not decide whether a skill should **exist**, whether two skills should
be **one**, or where a phase boundary belongs. Those are design judgements —
ADR 0091's entry-point fold is an example of one — and they are settled in ADRs
and with the user, not by grading.

It also inherits the limit its sibling states plainly: evidence is only as good
as the build it was measured against. A dimension that passed against an
installed build older than the source under review is not evidence about the
source. See `acs-evals/dataset/manifest.json` for which build the current
figures describe.
