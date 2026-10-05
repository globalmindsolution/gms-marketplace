# 0133 — An analysis is a folder: a README plus one file per bounded context

**Status**: Accepted — amended by [0134](0134-api-contract-is-a-design-document.md) (the `README.md` no longer carries `api_surface` or an API-surface verdict) · **Date**: 2026-10-05

**Amends**: [0114](0114-analyze-requirements-controller-driven-loop.md) (the
loop's draft is a folder, `iter-<n>/analysis/`; the deterministic checks run on
every file of it, and the publish copies and records every file instead of one)
and [0128](0128-requirements-from-any-container.md) (the Discovery and
Development folders hold an `analysis/` folder where they held an
`analysis.md`; the phase folders themselves do not move). The share-or-keep-local
choice of [0132](0132-share-or-keep-run-documents-local.md) applies to the
folder unchanged: kept local, it is `steps/analyze-requirements/local/analysis/`.

## Context

`/acs:analyze-requirements` published one `analysis.md`: scope, impact map,
questions, assumptions, risks, refined acceptance criteria and the verdict, in
one file. A change that crosses checkout, payments and notifications produced
one impact map with every area's components, files and tests interleaved, and
one risk list where a reader could not tell which risk belonged to which part
of the system. The file grew with the number of areas the change touched, not
with how much any one area changed.

The survey was already split by area: one `impact-analyst` lane per code area
(ADR-0114), merged by a synthesis pass into one set of notes, then drafted back
into one document. The structure the analysis had while it was being made was
thrown away when it was written down.

The readers paid for it twice. A person reviewing the PR, or reading a
feature's living analysis before designing it, scrolled one long page to find
the part they owned. Every later skill — `/acs:create-impl-plan`,
`/acs:create-test-docs`, `/acs:create-api-contract`, `/acs:create-design`, the
LLD skills, `/acs:code` — read the whole file into context to use the part that
concerned it.

## Decision

1. **An analysis is always a folder**, `analysis/`, never one long file — even
   when the change touches a single context. It holds:
   - **`README.md`**, the entry file (it renders on the forge when the folder
     is opened; never `index.md`): the scope and summary, the refined
     acceptance criteria (`AC-n`), the cross-cutting risks and decisions, the
     open questions, the API-surface verdict, and a table of contexts linking
     each context file with a one-line purpose.
   - **One file per bounded context** the requirements touch, named in plain
     words, kebab-case (`order-checkout.md`, `payment-refunds.md`): the
     context's impact map (components, files and tests, each cited
     `file:line`), its rules and edge cases, its risks, its open questions and
     its API notes. A context file never restates another's content; it links
     to it.
2. **Contexts come from the survey.** The impact analysts' code areas and the
   PRD features the requirements name are the candidates; the analyst names
   each context in plain words a reader would use, not after a directory. The
   impact reviewer judges every file, and the README's contexts table against
   the files present.
3. **Locations are ADR-0128's, one level down.** Discovery
   `<prd_dir>/features/<feature>/analysis/` (the feature's living analysis);
   Development `<development_dir>/<feature>/<ticket-id or run-id>/analysis/`;
   kept local (ADR-0132) `<run>/steps/analyze-requirements/local/analysis/`.
   The loop's draft is `steps/analyze-requirements/iter-<n>/analysis/`.
4. **The checks hold the shape, the agents do not.** `analysis record-draft`
   checks the draft folder before the review sees it:
   - `README.md` exists and no `index.md` does; every file name is kebab-case
     `.md`;
   - `README.md` carries the full front matter — `ticket` or `feature`,
     `ready_for_planning`, `api_surface`, `needs_design_recommendation`, plus
     ADR-0122's version keys on a Discovery analysis — and its required
     headings in order, and its contexts table links only files that exist and
     lists every context file;
   - each context file carries `context: <slug>` (plus `feature` and the
     version keys on Discovery) and its own required headings.
   A finding fails the iteration as a reviewer's does (ADR-0125).
5. **Publication copies the folder.** `analysis publish` copies every reviewed
   file byte-for-byte into the target folder, removes a context file the new
   analysis no longer has — only inside that `analysis/` folder, never beside
   it — and records each file's sha256; `analysis record-publication` verifies
   every one. It still stages, commits and pushes nothing (ADR-0127).
6. **Readers open the README first.** Every skill that reads the analysis
   reads `README.md`, then only the context files its work needs. `acs.py
   artifacts show` keeps the `artifacts["analysis.md"]` key for compatibility
   and returns the folder's `README.md` there, and adds `analysis_files`, every
   file of the folder, README first. `acs.py docs where --doc analysis.md`
   resolves the folder. `acs.py design list` shows a feature's living analysis
   as one group with its files, README first, each with its own status.
   `/acs:create-pr`'s commit plan groups the folder as one documents group.
7. **A single `analysis.md` is still read.** An analysis published before this
   change — a phase folder's `analysis.md`, or a legacy
   `docs/tickets/<ID>/analysis.md` — is read where no `analysis/` folder
   exists, by `artifacts show`, every reader and the next analysis' survey,
   which starts from it and writes the folder. Nothing converts it in place.

## Consequences

- An analysis loop that is mid-draft when this lands still holds a single-file
  draft; it stops with a missing-artifact error rather than migrating. Re-run
  `/acs:analyze-requirements` for that run: the published analysis it reads as
  input is unchanged, and the next draft is a folder.
- A reviewer opens the folder and lands on the README: what the change is,
  what is decided and what is still open, and a table saying where to read
  next. A context's owner reads one file.
- Later skills load the README and the context files they need, not the
  whole analysis; a plan slice or a test-case slice reads its own context.
- The analysis is more files to review, and the README table is one more thing
  to keep true. The check makes it fail loudly when a link or a file is
  missing, so it cannot drift silently.
- A context removed by a re-analysis is deleted from the folder on publish, so
  the folder always matches the README; anything else beside the folder is
  never touched.
- Naming a context is a judgement the analyst makes and the reviewer can
  challenge. Two runs over the same feature may name contexts differently; the
  re-analysis renames by publishing the new set, and the stale files go.
- Consumers that read `artifacts["analysis.md"]` keep working, now on the
  README; one that needs the impact map follows `analysis_files`.
