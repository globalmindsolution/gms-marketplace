# /acs:code — the changeset review

*Read by whichever `code` leg is running. Path:*
*`${CLAUDE_PLUGIN_ROOT}/skills/code/references/verify.md`.*

The verify phase IS the changeset review — there is no separate review skill.
The dimensions below, the verdict rules and the coverage hard fail are the
same on every delivery path. What a path decides is HOW the verifier is
spawned (one pass, or four lenses merged) and how many of the dimensions it
owes; each leg's SKILL.md says which, and that is the only place to look.

---

## The dimensions

Spawn the verifier AFTER all executors finish, with `<inputs>` of the branch
diff (`git diff <default-branch>...HEAD`), all `<partition>/specs/*.md`, the
ticket document, `<design_doc>` when it applies, the resolved
`plan.md`, and `test-cases.md` / `api-contract.md` when they exist. The verify
`<task>`'s
`<constraints>` always carry `<constraint name="audience_style_profile">engineers
(implementation-contract prose)</constraint>` — the register the folded plan
content (or the plan's own analysis/decomposition prose) is judged against. The
verifier judges fresh — never forward executor reasoning — and RE-RUNS the
tests and coverage itself (artifact `steps/code/iter-<n>/verify.md`).
Dimensions, each producing blocking findings on failure:

- **Acceptance-criteria conformance** — the ticket's `acceptance_criteria`/
  DoD re-read fresh every iteration from the ticket document, never the plan
  artifact's restatement; the AC-to-implementation matrix is rebuilt from
  scratch each time. When `test-cases.md` exists, each AC row of the matrix
  cites the `TC-n` ids that cover it, and a case with no test is a finding.
  Carries the completeness (five mandatory sections substantive, no
  stubs) and structure (`structure_lint.py` against the fixed five-heading
  literal) sub-checks when the fold is active.
- **Tests** — full suite passes; new tests genuinely exercise the spec's
  acceptance criteria (re-run, not trusted).
- **Coverage** — measured coverage meets `settings.test_coverage_percent`.
- **Business logic** — the behavior is correct, edge cases handled.
- **Features** — the changeset satisfies the ticket and its acceptance
  criteria, not just the letter of the specs.
- **Quality** — readable, maintainable, no dead code, no debug leftovers.
- **Technical standards** — repo conventions, lint clean, idiomatic for the
  stack; `standards_path` is included in the verifier's `<constraints>`
  when set, so `standards/` at that path is checked as this dimension's
  source of truth (changeset-scoped: introduced violations block,
  pre-existing ones surface as notes).
- **Architecture & system design** — judged against `design.md` when one
  exists (own or parent); otherwise against the documented architecture and
  sane structure; also against the folded plan artifact's Approach/API-data-changes
  content when no separately-authored spec set exists. Carries the
  **contract-conformance sub-check** when `api-contract.md` exists: every
  endpoint/command/message it specifies is implemented with the declared
  request/response shapes and error codes, and the changeset adds no public
  surface the contract does not describe.
- **Security** — no injected vulnerabilities, secrets, or unsafe handling of
  input/authz.
- **Documentation** — per-commit doc updating (README/API/usage docs/
  changelog/the architecture doc set/`lld/flows/`/ADRs, and the living
  requirements) is now `docs-sync`'s responsibility; when `/code`'s own
  verifier still notices a gap it reports it advisory
  (`severity="info" dimension="documentation"`), never blocking.
  **Product-doc-consistency check:** verify whether the
  changeset leaves factual claims in `docs/product/prd.md` or
  `docs/product/roadmap.md` stale (see the factual-vs-intent boundary in
  Execute step 4 above). A stale factual claim is a blocking finding
  (`severity="blocking" dimension="documentation"`). An intent contradiction
  is an explicit flagged divergence — NOT a block; it surfaces in the result
  document and PR body. No factual impact → no-op for this check.
- **Simplicity & scope** — overcomplication and out-of-scope edits are
  blocking findings (executor **Simplicity First** + **Surgical Changes** rules).
- **Audience-style** — the folded plan artifact's prose (or the plan's own
  analysis/decomposition prose when the fold is not active) matches
  `audience_style_profile`; an UNWAIVED register mismatch is a blocking
  finding, waived to `severity="info"` for a register the coordinator
  recorded via `clarify.py add --skill code --source assumption`.
- **Regression-risk (git-history)** — the `standard` and `complex` paths only
  (dimension 14; lens D on `complex`); git history on touched paths shows a
  prior revert/hotfix pattern on the same lines, or the diff reintroduces
  something a prior commit deliberately removed.
- **Plan conformance** — blocking when active, N/A otherwise (dimension 15,
  lens C); the verifier computes activation itself from
  `steps/code/plan-approval.json` (never a coordinator-relayed
  value): an eligible record whose `plan_path` is `phases/code/plan.md` and
  whose `plan_sha256` matches the current `plan.md` bytes. When active, a
  changed file tracing to no entry of the approved
  `## Executor tasks & file map`, or an implementation contradicting the
  approved Approach, is a blocking finding — strictly subordinate to
  Acceptance-criteria conformance (dimension 1), which an approved plan can
  never substitute for.
- **Path audit** — blocking (dimension 16; lens B on `complex`). Read
  `delivery_path` and `delivery_path_reason` from `run.json` and
  judge the CHANGESET against them: does the diff you actually have in front of
  you look like the work that reason describes? A changeset that contradicts
  its path — a `trivial` run that rewrote an authentication boundary, a
  `small` one that grew to thirty files across four components — is a blocking
  finding naming both the recorded reason and what the diff really does.

  This is the one dimension that judges the ROUTING rather than the code, and
  it exists because the path is chosen once, from a plan, before any code is
  written (ADR-0095). Nothing downstream re-checks that judgement, so if the
  plan understated the work, this is where it surfaces. The remedy is never to
  re-route mid-run: report it, and let the coordinator fail the run with
  `stop_reason: plan_superseded`, which sends /acs:ship back to
  `/acs:create-impl-plan` and re-classifies from a corrected plan.

---

## The verdict

**The verdict is the verifier's, not yours (MAR-527).** Each verifier writes
`steps/code/iter-<n>/verdict.json` (lens-scoped on `complex`) with
its per-dimension results and findings, and the SubagentStop hook refuses an
answer whose verdict is missing or does not hold together — in particular
`passed` must agree with the findings. Read it; never conclude it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" verdict merge --iteration <n>   # full depth: the 4 lenses
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" verdict show  --iteration <n>
```

`merge` is arithmetic over the lens files (conjunction of `passed`, union of
findings, worst result per dimension), not a second opinion; on the three
single-verifier paths there is one verdict and only `show` applies. It merges all four lenses or
none, and refuses to replace a verdict carrying blocking findings with a
passing one.

**`states.verifier_passed` is not yours to write.** Since MAR-523 the post
hook DERIVES it from `iter-<n>/verdict.json` and ignores whatever the result
document says, so `show` is for YOUR reading — to know whether to iterate —
not a value to transcribe. The derivation refuses a verdict that belongs to a
previous run, names another ticket or skill, or does not report every
dimension it owed; in each case `verifier_passed` is false and the
`/acs:create-pr` gate stays shut, with the reason recorded on the run entry.

ALL findings block — zero findings = pass. On
findings: persist the verify output, then AUTOMATICALLY re-execute, passing
every finding to the next iteration's executor(s) in `<context>` with no
planner spawn in between (TDD still applies to fixes: failing test first when
a finding is behavioral). After this path's iteration ceiling — each leg's
SKILL.md states its own — with findings remaining: stop with final status
`"failed"`, findings recorded, gate closed.

---

## Coverage hard fail

If the coverage target CANNOT be reached after honest effort: HARD FAIL the
run immediately — status `"failed"`, `states.tests.coverage_percent` set to
the achieved number, the reason in `stop_reason`, `verifier_passed: false`
(the /acs:create-pr gate stays closed). Do not lower the bar, do not pad with
meaningless tests, do not proceed to further specs.
