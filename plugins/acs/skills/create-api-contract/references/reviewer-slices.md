# Reviewer slices — who judges what, and how the slices' verdicts combine

Read this before every review: the eight dimensions' split across three
slices, how they are spawned, how their findings are de-duplicated after the
join, and the pass rule.

The contract-reviewer has eight check dimensions, so every review runs as
three fresh instances of the SAME agent, one per slice, each told its
dimensions in `<constraint name="dimensions">`:

| slice | dimensions | owns the check |
| --- | --- | --- |
| `surface` | 1 `completeness`, 2 `accuracy`, 7 `scope` | re-deriving the surface from the plan (or the subject) and the code |
| `trace` | 3 `traceability`, 4 `compatibility`, 8 `authoring-conformance` | `clarify.py list` against the ledger |
| `files` | 5 `contract-files`, 6 `front-matter` and `structure` | `front_matter_check.py`, `structure_lint.py`, the contract files as they stand in the working tree (`acs.py changes diff --name-only`) |

Spawn the three in ONE message — one Agent call per slice, all in the same
assistant message, in the foreground (three is within the default
`settings.parallel.max_agents` of 4; a lower setting runs them in waves of
that size) — and wait for ALL of them. Each writes
`iter-<n>/contract-reviewer-<slice>.md`; you join them, in the table's order,
with the `notes merge` command in SKILL.md's Reviewer slices.

**De-duplication — the join is the synthesis.** The slices own disjoint
dimensions, so the merge is the synthesis; you additionally drop a finding
that cites the same location and the same defect as another slice's finding,
keeping the one with the higher severity, and say so in the joined report:
append a `## De-duplicated findings` section to
`iter-<n>/contract-reviewer.md` naming each dropped finding, its slice, and
the kept finding it duplicates. Two findings on the same location for
different defects are both kept.

**The pass rule for sliced reviewers.** The iteration passes only if EVERY
slice returned `status="completed"` with zero blocking findings. Any slice's
blocking finding blocks, and all three slices' findings — de-duplicated,
otherwise verbatim — go to the next contract-author. A slice that returned
`status="failed"` or no usable `<result>` (after the one re-request) fails
the iteration exactly as a blocking finding does —
never "pass with a missing slice".
