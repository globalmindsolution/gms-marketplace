# The contract-author's passes — survey, write, and their early exits

Read this when you task a contract-author: what the survey pass and the write
pass are asked to do, what happens when one asks a question, and the
documents' shapes they write to.

## Objective, the survey pass (iteration 1, `slice="survey"`)

Enumerate the interfaces. From the requirements, the analysis, the design, the
HLD and the code, record in the authoring notes
(`steps/create-api-contract/iter-1/authoring.md`): the **Interface inventory**
— one entry per interface the acceptance criteria add, change or remove, its
kind, its slug, its existing `lld/<feature>/api/` document or "new", the code
that implements it today (`path:line`) and the `hld/integration-map.md` row it
details; the **Item list** — per interface, every operation, command, message
or signature, NEW / CHANGED / REMOVED, its current shape from the code (or
"new"), the acceptance criterion it traces to and the compatibility question it
raises; the **Conventions** the HLD and the code settle; the per-interface
outline of the document to write; and the genuinely open questions (a
versioning or breaking-change decision nothing settles is exactly such a
question). The survey writes no document and no fragment; its report is
`iter-1/contract-author-survey.json` (`interfaces` — the slugs and their
target paths — `items`, `questions`). The inventory decides the write: one
interface → one writer, two or more → Writer slices.

## Objective, the write pass

Each writer (`slice="write"` un-sliced, or one slice per interface) writes its
interface documents IN PLACE under `<architecture_dir>/lld/<feature>/api/`,
each with the six headings the Output contract names and its version front
matter through `acs.py design` (`design init` for a new file, `design bump`
for a changed one — once per run: a document this run already created or
bumped is edited without another bump on later iterations); its notes
`iter-<n>/authoring-<k>.md`; its fragment of the run record
`steps/create-api-contract/api-contract-<k>.md` — the run record's five
headings in order, no front matter and no title, only its own rows; and its
report `iter-<n>/contract-author-<k>.json` (`<k>` is `write` un-sliced). The
coordinator derives the record's front matter and joins every fragment, so
every run, sliced or not, ends in the same join (Writer slices).

## When a contract-author asks

If a contract-author returns `needs_input` with `<questions>`, resolve them in
User interaction and re-run it for the same iteration with the answers in
`<context>`. A survey that finds no interface the acceptance criteria touch
returns `needs_input` with the question "which interface does this change?" —
never an empty contract and never a padded one.

## The interface document's skeleton

```markdown
---
status: "proposed"
version: 1
tickets:
  - "SHOP-123"
feature: "bulk-import"
---

# Imports API — REST

## Scope
## Surface
## Error model
## Compatibility & versioning
## Examples
## Traceability
```

The front matter is written by `acs.py design init`, never by hand. `##
Surface` carries one `### ` subsection per item — what each holds is defined
in `create-api-contract-contract-author.md`. The run record's skeleton is in
SKILL.md's Output contract: `items` in its front matter is the number of `### `
subsections under `## Surface` across the interface documents this run wrote
or changed, and `interfaces` is their repo-relative list.
