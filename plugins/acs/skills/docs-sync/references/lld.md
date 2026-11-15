# The `lld` doc area — the feature's living LLD (ADR-0137)

Read when the run names at least one feature (`context.requirements.features`, or the
ticket's `features`). The coordinator, the `lld` doc-updater and the drift-reviewer's
`lld-currency` dimension all read this file. With no feature the area has no work: no gap
analyst, no `lld` doc-updater, and the report says so.

## What the area owns

Every path under `<architecture_dir>/lld/<feature>/api/`, `…/data/`, `…/flows/` and
`…/components/` for each of the run's features — the living documents
`/acs:create-api-contract`, `/acs:create-data-design` and `/acs:create-flows` write and
version (ADR-0122). The longest-prefix rule is unchanged, so `architecture` keeps the HLD
and the legacy flat `lld/flows/`. The per-run record folders `lld/<feature>/<key>/`
(`tech-design.md`, `api-contract.md`) are never edited by docs-sync, in any area. docs-sync
never creates a feature's first document of a type — that is its Design skill's job; a gap
with no document to land in is named in the notes with the skill to run.

## Gap analysts — iteration 1

Spawn one `acs:docs-sync-gap-analyst` per feature that has a living LLD document
(`context.agents.gap-analyst`; `slice="<feature>"`) in the SAME message as the
`requirements`, `architecture`, `adr` and `general` doc-updaters — gap analysts first when
`settings.parallel.max_agents` forces waves. Each task carries `<constraint name="feature">`,
`architecture_dir`, `partition`, `checkout_root`, and in `<inputs>` that feature's living
documents, `requirements.md` and the changeset command. A feature with no living document
gets no analyst. Join, once every analyst returned:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/docs-sync/iter-1/gaps.md \
  <partition>/steps/docs-sync/iter-1/gaps-<feature>.md …
```

Then spawn the `lld` doc-updater — after the join, because it reads `iter-1/gaps.md` —
beside any area the cap held back. A gap analyst that failed is re-requested once; still
failing, the run fails. On iterations 2-3 a `lld-currency` finding against a gap note
(`file` a `gaps-<feature>.md`) re-spawns that feature's analyst with the finding in
`<context>`, writing `iter-<n>/gaps-<feature>.md` (re-joined into `iter-<n>/gaps.md`); the
latest note per feature is the one Finish flips from.

## What the `lld` doc-updater does with the gaps

It never silently rewrites a contract. Per document, by its `status` in the gap notes:

- **`proposed`** (or no status block yet): `undocumented` / `drifted` → update the document
  to match the code, then `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design bump
  --ticket <id> <doc>` (`--ticket` only when the run has one); `unimplemented` → leave it
  (planned, still proposed).
- **`approved`** or **`implemented`**: ANY `drifted` or `undocumented` element is a
  question for docs-sync's ONE grouped ask — the doc-updater returns `needs_input` with one
  question per document and element, and edits that document only once a recorded answer is
  in its `<context>`. Each question reads: "The code differs from the approved `<doc>`
  (`<element>`: `<code path:line>` vs `<doc heading>`). (a) Update the document to match
  the code — it is bumped and set back to `proposed` for re-approval — or (b) keep the
  document: the code is wrong, a blocking finding for /acs:code."

  Answer (a) → the edit plus `acs.py design bump` (which re-opens it as `proposed`). Answer
  (b) → the document is untouched, and the coordinator records the element as a blocking
  finding (`file` the document, the element and both citations) and finishes `failed`, the
  summary naming `/acs:code <id>` to bring the code back to the design.
- **`deprecated`**: never touched.

Every document it edits is bumped, listed in its report's `files`, and its notes cite the
gap entry each edit resolves.

## The approved-drift ask, headless

These questions are NEVER auto-answered: no `--source assumption`, no default. When the
user cannot be reached (headless, or under `/acs:ship` with no answer relayed), record each
question `open` (`clarify.py add --skill docs-sync` without `--answer`), leave the document
as it is, and finish `interrupted` with `"stop_reason": "needs_input"`, each open drift in
`findings` — the resumed run re-spawns the `lld` area with the answers in `<context>`.

## The flip — `approved → implemented`, at Finish

Only after the drift review passed: for each document the latest gap notes mark
`implemented-candidate` whose status is still `approved` (re-read it with `acs.py design
check`; a document this run bumped is `proposed` and is not flipped), move them in ONE
atomic call:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design status --set implemented --by acs --reason "<run-id>: the code matches" <doc> [<doc> …]
```

It records `status_by`, `status_at` and `status_reason`. A document with any element still
`unimplemented` stays `approved` — partial delivery across tickets — and so does one a
`lld-currency` finding left in doubt. List the flipped paths (repo-relative) in result
`states.implemented` — the post-hook re-derives that list from each document's front matter
and drops any path that does not read `implemented` — and every document the `lld`
doc-updater edited and bumped in `states.files`.
