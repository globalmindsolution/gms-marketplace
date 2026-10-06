# /acs:analyze-requirements — the analysis templates

Read this before the analysis draft is written — the analyst in its `draft`
pass, and the coordinator when the `draft` action is due: the README's and
each context file's exact front matter and headings, what each section
carries, how the files are written, and the load-bearing surfaces the Risks
must name. The survey and the synthesis need none of it.

## The folder

The `draft` pass writes a folder for people first: plain-word headings, short
sections, a README someone can read without opening anything else. Every file
name is `README.md` or kebab-case `.md` made of plain words (no `index.md`, no
subfolder, nothing else). The analysis is read by machines as well as people:
the README's front matter (`ready_for_planning` above all, which
`/acs:create-impl-plan` reads) is part of the deliverable, not decoration. Emit
exactly these keys, with
these types, and exactly these headings in this order (the task's
`<constraint name="mode">` and `<constraint name="feature">` say which front
matter applies).

The folder holds two kinds of file.

## The README — `README.md`

**The README** — `README.md`, readable on its own by someone who opens nothing
else: EXACTLY this front matter and these six headings, in this order:

```markdown
---
ticket: SHOP-123
ready_for_planning: true
needs_design_recommendation: false
---

# Analysis — SHOP-123: Accept CSV imports over 10 MB

## Scope and summary
## Contexts
## Refined acceptance criteria
## Cross-cutting risks and decisions
## Questions and assumptions
## Verdict
```

- **Front matter.** `ticket` is the ticket id; a run with no ticket writes
  `feature: <slug>` in its place. `ready_for_planning` is the
  verdict below, as a boolean. `needs_design_recommendation` is your
  design-significance verdict. Never invent another key and never omit one of
  the three — except that a Discovery draft (`mode` discovery: the feature's
  living analysis) opens with the ADR-0122 version keys before them: `status:
  proposed`, `version` (the living analysis's `version` + 1, or `1` when there
  is none), `tickets` (carried over from the living analysis, `[]` when there
  is none) and `feature`. There is no `api_surface` key (ADR-0134): an older
  analysis that still carries one is read with the key ignored, and none is
  written.
- **`## Scope and summary`** — the requirements in terms of this repository,
  in a few sentences: the behaviour that changes, for whom, what "done"
  means, and what is out of scope. Name every disagreement between the
  requirements' prose and the code, each citing the file that contradicts it.
- **`## Contexts`** — a table, one row per context file, linked by its bare
  file name (no `/`, no anchor); every context file is listed, and only those
  — the controller refuses a link that does not resolve and a context file
  the table does not list:

  | Context | File | Purpose |
  | --- | --- | --- |
  | CSV import | [csv-import.md](csv-import.md) | how an uploaded file becomes rows |

- **`## Refined acceptance criteria`** — every criterion of the
  requirements, quoted with its `AC-n`, marked `testable` / `ambiguous` /
  `untestable` / `contradicted` / `missing`, with the rewrite for each
  non-clean entry and its state: `confirmed (C-n)` when the user confirmed it
  and the coordinator recorded it (`requirements refine`, which also amends
  the ticket when there is one) — quote it as `requirements.md`'s
  `## Refined` now carries it; `rejected (C-n)`; or `proposed — open (C-n)`
  when unanswered. Never present an unconfirmed
  rewrite as applied. Name the context file(s) each criterion lands in.
- **`## Cross-cutting risks and decisions`** — only what spans contexts or
  the whole change: the interfaces it adds or alters (each named, or "none" —
  an interface change is designed with `/acs:create-api-contract`) and the
  design verdict with their reason, a
  risk two contexts share, a load-bearing surface (each linked to the context
  file that details it). One-context risks stay in that context file.
- **`## Questions and assumptions`** — one line per clarification entry, by
  its `C-n` id and status (`open`, `answered`, `assumed`), with the question
  and the answer, or the rationale when assumed. Every item of the notes'
  `## Questions for the user` appears here as its `C-n`; the ledger
  (`clarifications.json`) is the source of truth. Then the assumptions: only
  what the user did not answer, with why each is needed and what breaks if it
  is wrong (a ledger entry with `--source assumption` included). A default
  the user confirmed is an answer, not an assumption. `_None recorded._` when
  there are none.
- **`## Verdict`** — `ready_for_planning: true` or `false`, in prose, with the
  reason. `false` requires naming exactly what is missing and which open
  question would settle it — and the question must be one where every
  default could build the wrong thing (a contradiction with the code, a
  design document or an ADR; a behaviour the criteria depend on that nothing
  defines; a fork in scope). A detail with a conventional default — "prints"
  means stdout, a credential check is exact and case-sensitive, argument
  counts the requirements never mention are out of scope — is never a reason for
  `false`: the user confirmed or corrected it, or, unanswered, it is an
  assumption recorded in `## Questions and assumptions` with a proposed
  criterion rewrite.

## One file per context — `<context>.md`

**One file per context** — `<context>.md`, one per context of the notes'
`## Contexts`, named by its file name there: a kebab-case name made of plain
words (never `index.md`, no subfolder), with EXACTLY this front matter and
these five headings, in this order:

```markdown
---
context: csv-import
---

# CSV import

## Impact map
## Rules and edge cases
## Risks
## Open questions
## API notes
```

- **Front matter.** `context` is the file name without `.md`. A Discovery
  draft adds, after `context`, `feature`, `status: proposed`, `version` and
  `tickets` — the same values as the README.
- **`## Impact map`** — a table, and its FIRST column is a repo-relative path,
  because that column is how a reader sees what this change actually touches:

  | Path | Component | Change | Evidence |
  | --- | --- | --- | --- |
  | `src/import/api.py` | import API | new size branch on upload | `api.py:88` rejects >10 MB today |
  | `tests/test_import_api.py` | import API tests | new cases for the large-file path | covers `upload()` at `:41` |

  Source, tests, docs and configuration all belong here. Every row carries
  evidence you read. A file the change CREATES is a row too, marked as new.
- **`## Rules and edge cases`** — the business rules this context enforces
  that the change touches, and the edge cases a test must cover, each cited.
- **`## Risks`** — implementation and shipping risks in this context with
  their evidence and, where one exists, the mitigation the implementation
  plan should consider; a load-bearing surface named with its paths.
- **`## Open questions`** — the `C-n` entries that concern this context only,
  by id and status (the README holds the full list), or `_None._`.
- **`## API notes`** — the surface this context adds or changes (endpoint,
  flag, message, schema), cited, or `_None._`.

A context file never restates another's rows, rules or risks: it links to the
file that owns them (`see [payment-refunds.md](payment-refunds.md)`).

## Without a ticket, and on a Discovery run

On a run with no ticket the README's first key is `feature: <slug>` in place of `ticket:`, and its title
reads `# Analysis — <feature>: <subject>`. A Discovery run's draft — the
feature's living analysis — opens the README with the version keys of
ADR-0122 before the three above: `status: proposed`, `version` (the living
analysis's `version` + 1, or `1` for the feature's first analysis), `tickets`
(carried over from the living analysis) and `feature`; each context file then
carries `feature` and the same three version keys after `context`:

```yaml
---
status: proposed
version: 2
tickets: ["SHOP-120"]
feature: wishlist
ready_for_planning: true
needs_design_recommendation: false
---
```

## What the review holds the draft to

This skill is where the requirements' ambiguities are SUPPOSED to surface, so the
README's `## Questions and assumptions` and the ledger are the same set of
facts in two places: every question is a ledger entry, and that section names
each entry by its `C-n` id and its status, so the next skill can see what is
still open. A question that concerns one context only is also listed in that
context file's `## Open questions`, by the same `C-n`.

What each section carries is defined above; the
contract that matters here is that every context file's `## Impact map` is a
table whose first column is a repo-relative path (that column is what the
load-bearing-surface step below reads), that the README's front-matter values
agree with the sections beneath them, and that the answers show: the README's
`## Questions and assumptions` lists every `C-n` with its answer or status and
holds as assumptions only what the user did not answer, and
`## Refined acceptance criteria` states which criteria were confirmed into the
requirements (and so the ticket, when there is one). Keep every section short;
an empty one says `_None._`. The README summarizes and links — it never
copies a context file's rows.

## Writing the files

The analyst writes and revises every file through Bash with acs's own
writer — `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write <path>
<<'ACS_EOF'`, the file's content, then `ACS_EOF` alone on the last line; an
in-place revision reads the file and writes it whole again the same way —
never through the Write or Edit tool. The draft lives in acs's workspace,
in the main checkout (ADR-0136), where a session in a worktree is refused
any Write/Edit; and the runtime also refuses a subagent's Write/Edit of a
file named like a report ("Subagents should return findings as text, not
write report files"), so each attempt would be a turn lost before the same
content lands via Bash anyway.

## Load-bearing surfaces — name them in the context's `## Risks`

The impact map is the first place anyone can see WHAT this change touches, and
that is the single strongest input to the delivery-path judgement /acs:ship
makes later from the plan (ADR-0095). Nothing here writes a rigor setting —
there is no `stakes` axis any more, and this skill does not classify — but the
analysis is where the evidence for that judgement is recorded.

So when the impact map reaches a surface the repo treats as load-bearing —
authentication or authorization, payments, a migration or any stored shape, a
public API other systems call, concurrency or ordering, anything the repo's own
architecture docs flag — say so explicitly in that context file's `## Risks`, naming the paths, and
list it again, linked, under the README's `## Cross-cutting risks and
decisions`. A
risk entry that names a boundary is read by `/acs:create-impl-plan` (which
carries it into the plan's own Risks section) and then by whoever judges the
path, and it is what turns a one-file change into a `standard` or `complex`
run instead of a `trivial` one.

Prose, not a setting: what makes this work is that the risk is stated where a
reader will weigh it, not that a glob matched.
