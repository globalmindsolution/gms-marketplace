# /acs:create-prd — reviewer slices, the floor, the join and the pass rule

Open this before every review. "Above" below means SKILL.md's Review
section: the reviewer's inputs and constraints, and the checklist the
dimensions (numbered in `create-prd-reviewer.md`) check.

**Reviewer slices and the floor — every iteration, the default.** The review
has eleven check dimensions (numbered in `create-prd-reviewer.md`). The ones a
script settles are not an agent's: **the `floor` is yours**, run with Bash in
the SAME message as the reviewer spawn, as soon as the author has written the
set. The rest run as two slices, each a fresh instance of
`acs:create-prd-reviewer` whose task carries `slice="<id>"` and
`<constraint name="dimensions">` naming the dimension numbers it owns, beside
every input and constraint above:

| Slice | Dimensions | Owns the run of |
|---|---|---|
| `substance` | 2 feature → goal traceability, 3 measurable success metrics, 4 prioritization discipline, 5 constraint consistency, 7 plan conformance (the semantic ceiling), 11 audience-style | the fresh semantic read of `prd.md`, `roadmap.md` and every feature PRD, and of every entry in the notes' `## Code evidence`, `## Answer fidelity` (the plan's and each feature's notes) and `## Roadmap milestones` sections |
| `delta` | 6 roadmap coverage, 8 amend-mode diff discipline, 9 iteration 2+ regression check | `git diff` over the whole set (below) and the re-verification of every prior finding |
| `floor` | 1 required sections, 7 plan conformance (the deterministic floor), 10 structure and the version front matter | run by YOU, no agent: `prd_conformance_check.py` (the three-family check, whose code-evidence family re-opens every citation through the shared citation-check helpers it imports), `structure_lint.py`, `prd_feature_check.py` (the hub's index against the feature PRDs), `acs.py design check` and the heading check — each run here only, exactly once per iteration |

**The floor, in the reviewer's own commands** (dimensions 1, 7 and 10 of
`create-prd-reviewer.md`, which stay the definition):

```bash
grep -n '^#' "<prd>"; test -s "<roadmap>"          # 1: the eight sections, each non-empty; roadmap.md non-empty
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prd_conformance_check.py" \
  --plan <partition>/steps/create-prd/iter-<n>/authoring.md --mode <greenfield|brownfield|amend> \
  --repo-root <repo_root> --clarifications <partition>/clarifications.json \
  --prd "<prd>" --roadmap "<roadmap>" [--added-heading "<heading>" ...] \
  [--feature-notes <partition>/steps/create-prd/features/<slug>/notes.md ...]   # one per feature PRD
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/structure_lint.py" \
  --sections "<required_sections, verbatim>" --ordered "<prd>"
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prd_feature_check.py" \
  --prd "<prd>" --feature-sections "<feature_required_sections, verbatim>"   # 1, 2, 10 for the feature PRDs
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design check "<prd>" "<roadmap>" \
  $(find "<features_dir>" -name prd.md)   # 10: the version front matter of every document
```

In amend mode derive the `--added-heading` values yourself from `git diff --
"<prd>" "<roadmap>" "<features_dir>"` (and `git status --short -- "<features_dir>"`
for the new documents): every `+###`/`+####` heading line added to `roadmap.md`;
omit the flag otherwise. Each stderr `source:line: [rule] message` is one
blocking finding (dimension `Plan conformance`, `traceability` for the
`feature-*` rules of `prd_feature_check.py`, or `structure`); exit 2 is
itself a blocking finding, so a broken invocation never passes. Each problem
`design check` lists, and its `ok: false`, is a blocking finding of dimension
`structure`. Write
`iter-<n>/reviewer-floor.md` (`acs.py write`, as every file below) — one `## ` section per dimension (Required
sections, Plan conformance, Structure) with the exact commands and output,
then `## Findings` — so the join below reads it like a slice's report. The
floor's semantic ceiling (whether the documents actually reflect each recorded
answer, whether a resolved citation substantiates its claim, whether a matched
milestone maps to the intended epic) is not a script's call: the `substance`
slice judges it from the notes' corroboration sections.

Grounding policing applies in every slice. Write `iter-<n>/reviewer-slices.json`
(the two slices; the floor is not a slice), spawn the two slices in ONE message
beside the floor and wait for both. Then **de-duplicate**: the slices and the
floor own disjoint dimensions, so the join below is the synthesis, but two can
still report one defect (a missing section seen by two dimensions). Drop a
finding that cites the same location and the same defect as another slice's
finding, keeping the one with the higher severity, and record every drop —
which finding, from which slice, kept in favour of which — under
`## De-duplicated findings` in `iter-<n>/reviewer-dedup.md` (write `none`
there when nothing was dropped). Join the reports, in the table's order with
the floor between the slices as before, and the de-duplication record last,
into the one report every later reader reads:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/create-prd/iter-<n>/reviewer.md \
  <partition>/steps/create-prd/iter-<n>/reviewer-substance.md \
  <partition>/steps/create-prd/iter-<n>/reviewer-floor.md \
  <partition>/steps/create-prd/iter-<n>/reviewer-delta.md \
  <partition>/steps/create-prd/iter-<n>/reviewer-dedup.md
```

**Pass rule for sliced reviewers:** the iteration passes only if EVERY slice
returned `status="completed"` with zero blocking findings and the floor found
nothing. Any slice's or the floor's blocking finding blocks the iteration. A slice that failed or returned no usable result
fails the iteration — never "pass with a missing slice"; re-run that slice
once, and if it fails again the iteration counts as failed with its error as a
finding.
