# 0132 — Run documents are shared or kept local by a saved choice; acs asks before creating a docs folder

**Status**: Accepted · **Date**: 2026-10-05

**Amends**: [0128](0128-requirements-from-any-container.md) (a run's
documents go to their phase folder only when the repo shares them; kept local,
they stay in the run's step folder, and a phase folder that resolves only to
acs's built-in default is confirmed before it is created),
[0102](0102-documents-are-found-not-configured.md) (settings now record the
user's answers: `docs.share_run_documents`, and a `docs.*_dir` written when a
location is confirmed — documents are still found first, and nothing is
configured up front) and [0127](0127-only-create-pr-commits.md) (a run
document kept local is never in the working tree, so `/acs:create-pr`'s commit
plan never sees it).

## Context

ADR-0128 put every document of a run in the repo, one folder per phase:
`analysis.md`, `plan.md` and `test-cases.md` under
`<development_dir>/<feature>/<id>/`, `design.md` and `api-contract.md` under
`<architecture_dir>/lld/<feature>/<id>/`. ADR-0127 then had `/acs:create-pr`
commit them as the PR's first group.

Not every team wants that. A per-run plan or test-case list is working paper
for many teams: the PR description and the code carry the change, and a
`docs/development/` tree that grows one folder per ticket is noise they would
rather not review or keep. Other teams want exactly that record. acs chose for
them.

It also chose where. When a repo had no `docs.*_dir` setting and discovery
found no folder, `doc_layout` fell back to its built-in default
(`docs/product`, `docs/architecture`, `docs/development`) and the first skill
that published created that folder — a new top-level structure in someone's
repo that nobody had agreed to. A repo whose docs live in `documentation/` or
`site/content/` found an acs-shaped `docs/` beside them.

Asking every run would be worse than either: the answer is a team's (or a
person's) standing preference, not a per-ticket judgement.

## Decision

1. **Every per-run document is either shared or kept local**: `analysis.md`
   (a Development run's), `plan.md`, `test-cases.md`, `design.md`,
   `api-contract.md`. **Shared** is ADR-0128 unchanged — published to the
   phase folder in the working tree, committed by `/acs:create-pr`. **Local**
   — the document stays in the run's state folder
   (`<run>/steps/<skill>/…`, in the gitignored workspace); later steps still
   read it (`acs.py artifacts show` resolves it), and nothing of it reaches
   the repo. The **living documents** — the PRD and roadmap, the HLD, the
   LLD, a feature's living analysis — are always shared: they are the
   product's record, not one run's.
2. **The choice is asked once and saved**, as `docs.share_run_documents`
   (`true` shared, `false` local; absent means not decided). The first skill
   that would write a run document while it is absent adds two questions to
   its one grouped ask: share run documents in the repo, or keep them local?
   and save that for me (this machine, `.acs/settings.local.json`) or for the
   team (`.acs/settings.json`)? Later runs follow the saved value silently and
   name it in their completion report ("kept local (team default)", "shared to
   `docs/development/…`"). The settings cascade already lets a member's local
   answer override the team's. `/acs:setup` shows and changes it.
3. **acs never creates a new docs folder in the repo without an answer.**
   `doc_layout` reports, per kind (`prd`, `architecture`, `development`), the
   folder and its resolution `source`: `setting` (a `docs.<kind>_dir`),
   `discovered` (an existing folder found) or `default` (acs's built-in
   fallback). When the source is `default`, the first skill that would write
   there asks one question: use the proposed folder, give another
   repo-relative path, or keep documents local. A folder answer is saved as
   `docs.<kind>_dir` in `.acs/settings.json` — a repo's layout is the team's,
   so it is asked once per repo; "keep local" is saved as the share choice,
   with its scope asked as in 2. A living document's first write into a
   folder that does not exist yet (the PRD folder for `/acs:create-prd` or a
   Discovery analysis, the architecture folder for `/acs:create-architecture`
   and the LLD skills) asks the location only: living documents are always
   shared.
4. **Two CLI verbs carry it**, so a skill asks and records but decides
   nothing itself:
   - `acs.py docs where --doc <name> [--run R]`, where `<name>` is a run
     document (`analysis.md`, `plan.md`, `test-cases.md`, `design.md`,
     `api-contract.md`) or `living:prd` / `living:architecture` — prints
     `{ok, doc, path, share, location_source, needs, proposed_path}`: the
     target (repo-relative when shared, run-relative when local), the saved
     share value (`true`, `false` or `null`), the folder's resolution source,
     the questions still owed (`share`, `location`, or none) and the folder a
     `location` question proposes;
   - `acs.py docs decide [--share yes|no --scope user|team] [--location
     KIND=PATH]… [--doc <name>] [--run R]` — merges the answer into
     `.acs/settings.local.json` (`user`; kept out of git through
     `.git/info/exclude` when nothing ignores it yet) or `.acs/settings.json`
     (`team`; every `--location` goes there as `docs.<kind>_dir`), creating
     the file when absent and touching no other key, then prints what it
     wrote and the new `where` — of `--doc`'s document, else of every
     document — with a warning when a more specific settings file still
     overrides the saved share choice.
5. **An undecided write is refused, not guessed.** `analysis publish`, and
   every other code path that writes a run document into the repo, exits 2
   naming `acs.py docs decide` while `needs` is non-empty. A local decision
   publishes into the run folder and records that target in the step's
   `publication`. `artifacts show` / `run_docs` report `paths[name]` by the
   decision — the run step folder when local, the phase folder when shared,
   `null` plus `needs` when undecided — while `artifacts[name]` reads the
   existing file wherever it is (phase folder, run folder, legacy
   `docs/tickets/<ID>/`).
6. **Headless runs keep documents local for that run only.** When a skill
   cannot reach the user, it writes the run's documents locally, saves
   nothing, and says so in its report; the question is still owed to the next
   interactive run.

## Consequences

- A team that keeps run documents local gets PRs that carry only the change
  and the living documents; the plan, test cases and design of a run are still
  there for every later step of that run, and for `/acs:handoff`, which
  packages the run's steps (ADR-0131).
- A local run document has no reviewer outside the run: a team that wants its
  plans and designs read in review shares them. The choice is visible in every
  completion report, so nobody mistakes "not in the PR" for "not written".
- A local document lives only as long as the workspace: an archived or
  deleted run takes it along. That is the point of the choice, and the
  reason the living documents are not offered it.
- `/acs:create-pr`'s commit plan (ADR-0127) needs no special case: a local
  document is never in the working tree, so it is in no group and never
  `left_out`.
- The first run in a repo asks up to three more questions, in the same one
  grouped ask; every later run asks none. A repo with `docs.*_dir` already set,
  or with its folders already present, is never asked a location.
- Settings now hold answers as well as configuration. ADR-0102's rule —
  documents are found, not configured — still governs: a `docs.*_dir` is
  written only when discovery found nothing and the user named a folder, and
  `/acs:setup` still writes no value equal to a default.
- The file-map guard is unchanged: shared paths are guarded as before, and
  writes into the run folder were already allowed.
