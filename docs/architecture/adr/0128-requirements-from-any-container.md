# 0128 — Skills take requirements from any container; a run's documents live one folder per phase

**Status**: Accepted — amended by [0130](0130-prd-versions-and-set-doc-status.md) (the documents in the Discovery and Design folders are listed by phase and feature, `acs.py design list`, for a status move) · **Date**: 2026-10-04

**Supersedes**: [0090](0090-ticket-artifacts-in-repo-docs-tree.md) in part — its
in-repo ticket docs tree (`docs/tickets/<ID>/` with `ticket.md` and the ticket's
step documents). Its split by audience stands: documents a person reviews are in
the repo, the run ledger is in the workspace.

**Amends**: [0114](0114-analyze-requirements-controller-driven-loop.md) (the
analysis loop and its publish run on any subject, keyed by run),
[0120](0120-design-document-catalog-and-ticket-features.md) (a run's features come
from its requirements, not only from a ticket, and a feature slug also names the
Discovery and Development folders), [0127](0127-only-create-pr-commits.md)
(`/acs:create-pr`'s first commit groups are the run's documents in their phase
folders, not `docs/tickets/<ID>/`; the follow-up it named — every skill accepts a
prompt or a ticket — lands here), and
[0102](0102-documents-are-found-not-configured.md) (documents are still found, not
configured, by default; three optional `docs.prd_dir`, `docs.architecture_dir` and
`docs.development_dir` settings now name the phase folders for a repo whose layout
discovery cannot find — absent, discovery and the defaults apply).

## Context

A run already took a `ticket | prompt | document` subject, but only one, and only
the first token of the invocation: `/acs:analyze-requirements SHOP-12
~/Downloads/spec.pdf "also bulk export"` became a ticket run and the document and
the prompt were silently dropped. The run declared a `requirements.md` at its root
and created a `subject/` folder, and nothing wrote either; the two readers that
looked for `requirements.md` "when the run has one" never found it.

Several pieces required a ticket outright: the clarification ledger lived in the
ticket's partition, the analysis loop and its schema were keyed by `ticket_id`,
the analysis publish targeted the ticket's docs folder, `acs.py artifacts show`
and `ticket save` needed a ticket, `/acs:create-design`'s gate read the ticket's
`needs_design`, and `/acs:create-data-design` / `/acs:create-flows` stopped with
no ticket. So `/acs:ship "<prompt>"` failed at its first step, and the
`ship-raw-request` eval calibration had to skip that step.

The documents a run wrote went to `docs/tickets/<ID>/` (ADR-0090) — one folder per
ticket, beside neither the PRD feature it served nor the low-level design it
changed. A run without a ticket had nowhere to put them at all.

The user's decisions: a ticket id, documents (in the repo, or attached from outside
it — PDFs, images, markdown) and a prompt are only **containers** of requirements,
and may be mixed; documents from outside the repo are copied into the run, never
into the repo; no skill requires a ticket; tickets are no longer stored in the docs
folder; and a run's documents live in one folder per phase.

## Decision

1. **Requirements, not tickets.** Every skill's arguments are parsed into
   **sources** (`acs_lib.requirements.parse_sources`, `shlex` split): a
   `<PREFIX>-<n>` token is a ticket; a token naming an existing file —
   repo-relative, absolute or `~`-expanded — is a document; everything else is
   joined, in order, into one prompt. A run keeps ONE primary subject
   (ticket > document > prompt) as `run.json.subject`, so run ids and
   resume-by-ticket are unchanged, and records the full list as
   `subject.sources`. **No skill requires a ticket.** A ticket id that does not
   exist is still refused, naming `/acs:create-ticket`.
2. **Normalised once per run.** `requirements.materialise` — called by the
   Skill pre-hook that creates or adopts the run and by `acs.py step start`, so a
   hookless host gets it too — writes `<run>/subject/sources.json`
   (`[{kind, ref, sha256, copy}]`), copies each document from outside the repo to
   `<run>/subject/<n>-<basename>` with its hash, and regenerates
   `<run>/requirements.md`: a front block (run id, generated time, sources), then
   `## Ticket <ID>` (title, description, acceptance criteria numbered `AC-1…`,
   features, `needs_design`), `## Prompt` (verbatim), `## Documents` (text inlined,
   anything else cited by its run copy for the model to read) and `## Refined`.
   A later step invoked with new sources adds them (`acs.py requirements add`,
   deduplicated) and regenerates; nothing is replaced silently and the file is
   never edited by hand. `## Refined` is written only by `acs.py requirements
   refine` — `/acs:analyze-requirements`' refined criteria, `needs_design`,
   features and feature — which also patches the ticket when the run has one.
3. **Every skill reads requirements from the run**: `context.requirements` in the
   step-start context (`{path, sources, acceptance_criteria, features, feature,
   needs_design}`, for every run) or `acs.py requirements show`, never
   `ticket.json` for acceptance criteria. Ticket-only steps — `ticket save`,
   tracker sync — run only when there is a ticket.
4. **Ticket-optional plumbing.** A ticket run keeps its clarification ledger in
   the ticket's partition; a ticketless run keeps one at
   `runs/<run-id>/clarifications.json`. The analysis loop is keyed by `run_id` with
   an optional `ticket_id`, and an analysis's front matter carries `ticket` or
   `feature`. `/acs:create-design`'s gate reads `needs_design` from the run's
   requirements (refined, else the ticket's flag); a ticketless run with none
   recorded may run it when the user invoked it with requirements — the invocation
   is the ask — and the epic refusal stays ticket-only. `/acs:ship` passes its
   arguments to the first step for every subject kind.
5. **A ticket is not a document.** It lives in the workspace partition
   (`ticket.json`, its clarification ledger) and in the tracker. Nothing writes
   `docs/tickets/<ID>/` — no `ticket.md`, and no step document there.
6. **One folder per phase**, each keyed by the run's feature (the ticket's first
   feature or the one the analysis confirms; a ticketless run names one in
   `/acs:analyze-requirements`' one grouped ask, choosing among the PRD's slugs
   from `acs.py slug`, or a new slug when none fits):

   | Phase | Folder | Holds |
   |---|---|---|
   | Discovery | `<prd_dir>/features/<feature>/` | the feature's living `analysis.md` (ADR-0122 front matter plus `feature`) |
   | Design | `<architecture_dir>/lld/<feature>/<ticket-id or run-id>/` | `design.md`, `api-contract.md`; the living LLD subfolders (`api/`, `data/`, `flows/`, `components/`) are still edited in place (ADR-0126) |
   | Development | `<development_dir>/<feature>/<ticket-id or run-id>/` | a Development run's `analysis.md`, `plan.md`, `test-cases.md` |

   `<prd_dir>` is found the way `/acs:create-prd` finds the PRD, defaulting to
   `docs/product`; `<architecture_dir>` the way the Design skills find the set
   (`hld/tech-stack.md`), defaulting to `docs/architecture`; `<development_dir>`
   is an existing `docs/development/`, defaulting to it
   (`acs_lib.requirements.prd_dir`, `architecture_dir`, `development_dir`).
   A run's phase is Development when it has a ticket or `/acs:ship` drives it,
   else Discovery (`requirements refine` may set it explicitly).
   `/acs:analyze-requirements` on a Discovery run writes the feature's living
   analysis; on a Development run it writes the Development folder's
   `analysis.md` and starts from the living analysis when there is one.
7. **Read by run, legacy folders still read.** `artifacts.artifact_path`,
   `describe` and `acs.py artifacts show` resolve by run (`--run` or this
   checkout's pointer; `--ticket` keeps working). When a phase folder has no such
   file, an existing `docs/tickets/<ID>/<name>` is read instead, so tickets
   started before this change keep their documents. `acs.py artifacts migrate`
   is retired: it reports and writes nothing. The file-map guard keeps the
   legacy tree a control input and adds the run's Development and Design
   folders: an executor never writes the plan or test cases it is checked
   against.

## Consequences

- `/acs:ship "<prompt>"` runs from its first step, and the `ship-raw-request`
  calibration no longer skips `/acs:analyze-requirements`. A mixed invocation
  keeps every source it was given, and `requirements.md` names where each
  requirement came from.
- An attached document is evidence the run holds — copied and hashed — so a later
  edit or deletion of the original does not change what the run was asked. The
  repo gains nothing for it; the workspace grows by the copies.
- A feature's documents read together: its analysis beside the PRD, its design
  records beside its LLD, each change's plan and test cases under one feature
  folder. `/acs:create-pr` commits the run's documents per phase folder.
- **Breaking, user-visible:** new runs no longer write `docs/tickets/<ID>/` and no
  `ticket.md` is rendered. A reviewer finds a ticket's documents in its phase
  folders; its fields are `acs.py ticket show` and the tracker. Existing folders
  stay readable and nothing moves them. The `## Clarifications` mirror that
  `ticket.md` carried goes with it; the ledger was always the record.
- `status` stays derived (ADR-0090); with no `ticket.md` it has no second home to
  disagree with.
- A run files under ONE feature. A change spanning several features keeps its
  documents under the first (or confirmed) one; the living LLD it edits in other
  features' folders is recorded in `states.files` as before.
