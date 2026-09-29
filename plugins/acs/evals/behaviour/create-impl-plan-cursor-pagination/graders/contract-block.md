---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/plan.md }
pattern: '^## Contract[ \t]*$(?:(?!^## )[\s\S])*^delivery_path:[ \t]*(?:trivial|small|standard|complex)[ \t]*$(?:(?!^## )[\s\S])*^owes:[ \t]*$'
flags: m
---

The plan ends with the one fixed-shape section downstream code reads
(`acs_lib.plan_contract`): `## Contract` with a `delivery_path` from the four
paths `/acs:code` dispatches on, then the `owes:` table. "Not a template" is
not "no structure": a free-form plan without it gives `/acs:code` no leg to
run.
