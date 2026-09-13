# Evaluation rubric

What a case is worth, and what makes a run pass. Without this, every assertion
counts the same — and a suite that weighs "a verifier can claim to pass while
carrying a blocking finding" the same as "punctuation is stripped from a slug"
cannot tell a release engineer anything useful about risk.

Severity answers one question, and only one:

> **If this case fails on a released build, what can go wrong for a consumer?**

It is a property of the *assertion*, not of how hard the case was to write or
how likely it is to break.

## The three levels

### `critical` — the pipeline can produce a wrong or unauditable outcome

A failure here means acs can do real damage in a consumer repo: let unreviewed
work through a gate, merge on absent evidence, steal a lock another session
holds, or collide ticket ids. These are the assertions that exist because the
safe answer to "I cannot tell" is **no**.

A case is `critical` when its failure mode is one of:

- **A gate opens that should have stayed shut.** Pipeline ordering, the
  needs_design refusal, the epic refusal.
- **A fail-closed path fails open.** A truncated PR recording reading as
  "ready"; a lock with no readable age reading as stale; minting restarting a
  ticket sequence.
- **Evidence stops being evidence.** The verdict's derived-`passed` invariant,
  and the freshness rules that stop one run's clean verdict standing in for
  another's.
- **A guarantee the docs make to users is withdrawn.** The no-auto-invoke
  guarantee on `disable-model-invocation` skills.

**Release rule: a single `critical` failure blocks the release.** No exceptions,
no "accepted for this cut" — either the build is fixed or the case is proven
wrong.

### `major` — a documented contract moved

A failure means something a consumer or a coordinator *builds on* changed shape:
a CLI's JSON keys, a decision table's output, a schema's required fields or
enums, the set of shipped skills. Nothing is unsafe, but something downstream
will break or silently misbehave.

**Release rule: `major` failures block by default.** They may be accepted for a
release only if the change is deliberate, the golden is re-recorded in its own
reviewed commit, and the change is named in the plugin's changelog. Accepting
one without re-recording it is not allowed — that leaves the suite red and
trains people to ignore it.

### `minor` — drift with no downstream consequence

Wording of a message, formatting of a derived string, a mechanically generated
constraint edge on an optional field nothing reads. Worth knowing about,
because unexplained drift is often the first symptom of something larger.

**Release rule: `minor` failures do not block.** They must each be triaged to
one of the three outcomes in
[`EVALUATION-PROCESS.md`](EVALUATION-PROCESS.md#triaging-a-failure) before the
next release, not carried indefinitely.

## Assigning a severity

Severity is declared per group and overridden per case:

```json
{
  "group": "pipeline gates",
  "severity": "critical",          ← the group default
  "cases": [
    {"id": "GATE-001", "...": "..."},
    {"id": "GATE-002", "severity": "major", "...": "..."}   ← override
  ]
}
```

The runner resolves it exactly as it resolves `profile` and `covers`. A case
with no severity anywhere defaults to `major` — the assumption is that an
unclassified assertion matters until someone says otherwise, because the
failure mode of the opposite default is a critical assertion silently counted
as noise.

### Test

When a level is not obvious, ask in order:

1. *Could a consumer's repo end up in a bad state — unreviewed code merged, a
   lock stolen, ids collided — if this shipped broken?* → `critical`
2. *Would something that reads this output break, or quietly do the wrong
   thing?* → `major`
3. *Otherwise* → `minor`

Ties go to the **higher** severity. Over-classifying costs a conversation;
under-classifying is how a real defect ships green.

## The verdict

`make gate` reports one of four states:

| State | Condition | Meaning |
|---|---|---|
| **PASSED** | no failures at any severity | Ship it. |
| **PASSED (minor drift)** | only `minor` failures | Ship it, and triage the drift before the next cut. |
| **BLOCKED** | any `major` failure | Fix, or re-record deliberately and re-run. |
| **BLOCKED (critical)** | any `critical` failure | Stop. Do not cut a release from this build. |

Two conditions are reported alongside the verdict and are also blocking:

- **Off-baseline** — the build under test is not the build the goldens were
  recorded against. Not a defect, but it means "no regression" is unproven
  until the baseline is refreshed.

  **Not the version — the build.** An unreleased source tree carries the same
  `plugin.json` version as the release it supersedes, so comparing versions
  answered "yes, this is the baseline" for the source the dataset pins *and*
  for the older released build it was scores of cases ahead of, and this
  condition never fired in either direction. The manifest therefore records a
  `recorded_against_fingerprint` — a hash of the shipped skill surface, each
  skill with whether a model may route to it unaided — and 25 invocable skills
  is not 32 with six legs user-only, whatever the two `plugin.json` files say.
  `--record` re-stamps it, so a re-record cannot leave the baseline naming the
  previous build.
- **Coverage below floor** — `make mutation` measures what the schema tier
  would actually catch. Below 90%, a green run is weak evidence, and the gate
  says so. The floor was 50% while the measurement itself was wrong in two
  ways: it counted keyword occurrences that restrict nothing (an
  `additionalProperties: true` says exactly what its own absence says, so no
  case can ever pin it), and the case generator refused every constraint it
  could not reason about in advance instead of building the mutant and asking
  the validator. With both fixed, and every schema seeded, the tier measures
  **100% of the 224 constraints any instance could distinguish** — so a 50%
  floor gated nothing. A floor no run can fail is not a floor.

  The floor sits at 90 rather than 100 deliberately: the steady state is 100%,
  and the ten points are headroom for a schema that grows a constraint before
  the case pinning it is written, not licence to leave one unpinned. A drop to
  99% is a question to answer, not a budget to spend.

## Tier 3 has its own verdict, and its own reason

This rubric grades the **deterministic** tier: severity answers "if this case
fails on a released build, what can go wrong for a consumer" — that is, what
*breaks*. It has nothing to say about whether skills got better, cheaper or
faster, because tier 1 cannot see any of those.

Tier 3 grades that, with the same three severities and one extra rule: an
*absolute* floor (routing accuracy, run completion, unresolved blocking
findings) blocks, while a *relative* threshold (cost, time, iterations,
coverage) only reports until it has been calibrated against observed noise.
The states and the reasoning are in [`PERFORMANCE.md`](PERFORMANCE.md).

The two verdicts are reported side by side and neither subsumes the other. A
build can be PASSED on contracts and BLOCKED on performance; that is not a
contradiction, it is the point of having both.

## What this rubric does NOT do

It does not weight cases into a single score. A percentage — "97% passed" —
invites shipping on a number, and the whole point of the levels is that one
critical failure is not offset by three hundred passes. The verdict is a
**gate**, not a grade.

It also says nothing about whether the *behaviour being pinned* is correct.
Severity ranks the consequence of a case failing; whether acs should behave
that way in the first place is a design judgement this dataset deliberately
does not make. See [`METHODOLOGY.md`](METHODOLOGY.md).
