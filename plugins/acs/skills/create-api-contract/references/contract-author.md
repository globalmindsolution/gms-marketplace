# The contract-author phase — its objective, its early exits, and the draft's skeleton

Read this when you task the contract-author (and, on a sliced run, before you
write the preamble): what iteration 1 is asked to do, what happens when it
asks a question or finds no surface, and the draft's front matter and seven
headings.

## Objective, iteration 1

Objective, iteration 1: enumerate the surface. From the plan, the analysis,
the design and the code (or, with no plan, the subject and the code), record in
the authoring notes
(`steps/create-api-contract/iter-<n>/authoring.md`) one entry per
endpoint/command/message/schema/signature the plan adds or changes — each
with its kind, its current shape (or "new"), the plan item and acceptance
criterion it traces to, the compatibility question it raises, and which
machine-readable contract file (when the tree exists) describes it — plus the
genuinely open questions (a versioning or breaking-change decision the plan
does not settle is exactly such a question). Then write the contract draft
from those notes. The notes are what the contract-reviewer checks the draft
against.

## When the contract-author asks, or finds nothing

If the contract-author returns `needs_input` with `<questions>`, resolve them
in User interaction and re-run the contract-author for the same iteration with
the answers in `<context>`.

If the survey finds no surface at all — nothing the plan or the subject adds or
changes is an endpoint, command, message, schema, signature or persisted
format — the contract-author says so in its report (`items: 0`) and writes no
draft. Skip the contract-reviewer, publish nothing, and complete with
`outcome: no_surface_owed` and the survey's reason in `summary`.

## The draft's skeleton

The draft's front matter and its seven headings, in this order:

```markdown
---
ticket: SHOP-123
items: 3
contract_files: ["docs/api/openapi.yaml"]
---

# API contract — SHOP-123: Accept CSV imports over 10 MB

## Scope & sources
## Surface
## Error model
## Compatibility & versioning
## Examples
## Traceability
## Contract files
```

`## Surface` carries one `### ` subsection per item — what each holds is
defined in `create-api-contract-contract-author.md`. `items` in the front matter is
the number of those subsections, and `contract_files` is the repo-relative list
of machine-readable files this run changed (`[]` when none).
