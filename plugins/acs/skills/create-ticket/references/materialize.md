# /acs:create-ticket — materializing the confirmed ticket (Steps 3-5)

Open this once Step 2's user-confirmation gate has closed — or, in the
`--fan-out` and split/restructure modes, once their own confirmation has — and
follow it yourself, inline. /acs:create-ticket spawns no subagent for this:
materializing a ticket is a fixed sequence of commands (rewrite `ticket.json`,
mint an epic's children, sync the tracker) with nothing for a separate agent to
judge, so the coordinator that ran the analysis and the confirmation runs it
too. The confirmed decisions are binding here: you do not re-analyze or
re-decide while materializing. If the confirmed proposal turns out impossible
to write as confirmed, stop and say so (the Finish failure path in SKILL.md);
never improvise.

**Where the cross-references below point.** Step numbers (Steps 1-5),
`Resume & reconcile`, `User interaction` and `Finish` are SKILL.md's. Step 5's
full text is `${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/tracker-sync.md`;
the modes are `references/epic-fan-out.md` and `references/split-ticket.md`.

## What you work from

Everything below reads workspace state and the confirmed decisions, never a
paraphrase of them. Before writing anything, re-read:

- `<partition>/ticket.json` — its parent directory IS the partition;
- `steps/create-ticket/iter-<n>/authoring.md` when the analysis was persisted
  there, plus the clarification ledger (`clarify.py list`);
- the settings and template files you need: the built-in ticket templates
  (`epic-default`, `story-default`, `task-default`), `tracker_provider` (`local`|`github`) and whether tracker sync
  is on;
- the confirmed decisions: the final type, `needs_design` (`true` for epics —
  stated, never user-confirmed; otherwise `false`, never offered), the child
  list, a confirmed PRD divergence, and any conflict resolutions.

## GitHub call failure policy, as it applies here

Canon lives in `create-ticket/SKILL.md`'s own "GitHub call failure policy"
section — this reference classifies no `gh` call itself, it only
follows that classification (critical for the remote-import read; critical per
ticket, soft per batch for Step 5's `gh issue create` tracker-sync call;
non-critical for the labels/assignee/milestone/Projects v2 field-fill
checklist). Canon hint text (`acs_lib.GH_ACCESS_HINT`, selected by
`acs_lib.gh_failure_hint(stderr)`):

> This looks like a session-level access restriction — a Claude Code
> cloud/managed session must have the Claude GitHub App connected for this
> organization by an org admin. A local Claude Code session uses your own
> `gh` authentication and should not see this.

## Materialization steps, in this order

1. **Set the title**: an epic's title is prefixed `[EPIC] `; a story's and a
   task's is the title as given.
2. **Build the description** from the type's fixed built-in template
   (`${CLAUDE_PLUGIN_ROOT}/templates/<name>.md` — `epic-default`,
   `story-default`, `task-default`); a repo's own `<repo>/.acs/templates/<name>.md`
   of the same name replaces it. Fill EVERY section with real content from the
   confirmed proposal; delete the HTML comments.
3. **Rewrite `<partition>/ticket.json`**, PRESERVING `id`, `status`, and
   `created_at`, and setting every field required by
   `${CLAUDE_PLUGIN_ROOT}/schemas/ticket.schema.json`: `title`, `type`,
   `description`, `acceptance_criteria` (array of testable strings),
   `priority` (`critical|high|medium|low`), `parent` (null — this skill
   creates roots), `children` (`[]` on every creation run, including an
   epic's own — Step 4 fills it later, in a `--fan-out` or split/restructure
   run), `external` (the
   import mapping, the step-5 sync result, or null), `assignee` (or null),
   `story_points` (or null), `needs_design` (`true` for epics, `false`
   otherwise — never user-confirmed), `docs_only` (the confirmed value,
   default false), `due_date` (ISO-8601 date string or null), `features`
   (the confirmed PRD feature slugs; omit when none); refresh
   `updated_at` (ISO-8601 UTC).
4. **Epic fan-out** — runs in `--fan-out` mode or in the split/restructure
   mode — the two modes that mint children. The step-3 skip applies
   ONLY in `--fan-out` mode: step 3's root `ticket.json` rewrite above is
   skipped entirely in that mode, because the epic's own fields are never
   touched — only its `children` array changes. In the split/restructure
   mode, step 3 DOES run: the ticket becomes an epic (`references/split-ticket.md`)
   before its children are minted in this same step 4. For
   each user-confirmed child, run exactly:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/new-ticket.py" --title "Wishlist API" --type story --parent SHOP-123 --description "..." --priority medium --needs-design false --story-points 3 --features wishlist
   ```

   A child carries its epic's `features` unless the confirmed breakdown narrows
   them. The script mints the child id, writes BOTH link directions (child `parent`,
   epic `children`), and records the child's completed create-ticket run —
   children never rerun /acs:create-ticket; their pipeline starts at
   /acs:code. Capture each printed `ticket_id`. After minting, write each
   confirmed child's `acceptance_criteria` (from the confirmed breakdown)
   into that child's ticket with `acs.py ticket save`:

   ```bash
   printf '%s' '{"acceptance_criteria": ["...", "..."]}' \
     | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" ticket save --ticket <child-id> --from -
   ```

   `--ticket` names the child; `--from` takes a JSON file, or `-` (or nothing)
   for stdin. The document is a PATCH merged over the stored ticket, so send
   only `acceptance_criteria`. It writes the workspace partition's
   `ticket.json` — the ticket lives only in the workspace and the tracker,
   never in the repo (ADR-0128: nothing writes `docs/tickets/<ID>/ticket.md`
   any more) — and re-indexes it. Never hand-edit `ticket.json`. `new-ticket.py` exposes no `--acceptance-criteria` flag.

   Create ONLY the
   confirmed children; on a resumed run never re-mint ones already in
   the epic's `children`. Re-read `ticket.json` after fan-out.
5. **Tracker sync** — only when `settings.tracker.provider` is `github`;
   skip entirely for `local`.
   - **The "tickets to sync" set:** `[root ticket, unless it is an import] +
     [every child minted in step 4]`, EXCLUDING any ticket whose title is a
     product-flow delivery title (`PRODUCT_TICKET_TITLES`: "Product definition
     (PRD)", "Product architecture doc set") — those are never synced by this
     skill's fan-out (AC-4) — **and EXCLUDING any ticket whose `external` is
     already non-null**: a `--fan-out` run's "root ticket" is an
     already-synced epic, so applying this set literally would re-create its
     issue as a duplicate; only the newly minted children (whose `external`
     is still null) enter the sync set.
   - Imported tickets: keep `external` as pulled; NEVER create a remote
     duplicate. If your local title/description changed AND the remote also
     changed since the pull, do not pick a side: ask the user which version
     wins, stating both (SKILL.md's User interaction; a non-interactive run
     returns the `needs_input` handoff with that question), then continue.
   - **For each ticket to sync in the set above**, run the sequence below,
     once per ticket:
     - `github`: one command performs the whole batch — issue creation,
       labels, assignee, milestone, Project membership, `Type`/`Status`, and
       the Priority / Story Points / Parent fields the board defines:

       ```bash
       python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" tracker sync \
         --ticket <id> --ticket <id> ...
       ```

       It applies the exclusion rules itself and posts each partition's
       `tracker-body.md` as the issue body — **write that file first**, from
       the ticket's rendered description, for every ticket in the batch. The
       body is what the issue is made of, so a partition without one is not
       synced at all: the command reports that ticket under `failed` with an
       `error` finding naming the missing path, and never creates a bodiless
       issue. Read the printed JSON: `synced` maps a ticket id to
       its `external`, `failed` lists the ids whose issue creation failed. A
       board that defines none of a field's accepted names is one info finding
       naming the skipped field; a ticket whose own `priority`/`story_points`/
       `parent` value is `null` is skipped silently, no finding — a null value
       is expected data, not a gap. Record the printed `findings` verbatim as
       the `project_fields` object per synced ticket.
   - Write `external` into each synced ticket's own `ticket.json` — root and
     every child — via `python3
     "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/record-external.py" --ticket
     <ticket-id> --provider <provider> --key <key>` once per successfully
     synced ticket. A failed `gh` call for any one ticket in the set
     is **critical (per ticket), soft (per batch)**: it produces an
     **error**-severity finding naming that ticket's id, the verbatim
     error, and the canonical hint from `acs_lib.gh_failure_hint`,
     `replayable: false`, surfaced in the result document's `errors` and the
     `<handoff>` — never silently swallowed — and does NOT abort the batch:
     continue to the next ticket in the set; the failed ticket's `external`
     stays null (never fake a key). When any required ticket in the set
     failed, the run's overall status is `failed` (or `completed` with a
     blocking finding); list which tickets synced (with their key) and which
     failed (with the error) so the failed ones can be retried individually.
6. **Write the materialize report** to
   `steps/create-ticket/iter-<n>/materialize.json`: artifacts
   produced, files changed, commands run with outcomes, problems hit, and the
   confirmed decisions you applied.

## The materialize report

`iter-<n>/materialize.json` is the audit record of what steps 1-5 did; the
result document (SKILL.md's Finish) summarizes it and never inlines its
detail. The example below shows a `--fan-out` (or split) run that minted
children; a plain creation run carries no `children` finding — `children`
stays `[]`:

```json
{
  "status": "completed",
  "files_changed": [
    "/abs/path/to/partition/ticket.json",
    "/abs/path/to/child/partition/ticket.json"
  ],
  "commands": [
    {"cmd": "python3 .../new-ticket.py --title \"Wishlist API\" --type story --parent SHOP-123 ...", "outcome": "minted SHOP-124"}
  ],
  "findings": [
    {"severity": "info", "dimension": "children", "detail": "minted SHOP-124, SHOP-125"},
    {"severity": "info", "dimension": "external", "detail": "synced as github 789"}
  ],
  "decisions_applied": ["type epic (C-1)", "children SHOP-124, SHOP-125 confirmed at the fan-out gate"],
  "problems": []
}
```

- `files_changed` lists every file you wrote or changed, including each
  child's partition `ticket.json` (workspace state — no ticket file enters the
  repo).
- `status: "failed"` with `problems` when a step cannot complete (keep what
  you finished — never roll back minted children), then take SKILL.md's Finish
  failure path; the only question this sequence ever raises is the
  sync-conflict case above.

## Hard rules

- Spawn no subagent for any of this: the steps above are ordered commands the
  coordinator runs itself.
- Mutate ONLY what the confirmed proposal covers: the ticket partition (child
  partitions via `new-ticket.py`, plus the confirmed `acceptance_criteria`
  written into each minted child's ticket via `acs.py ticket save` after
  minting) and the
  remote tracker. Never touch consumer-repo source,
  never create branches/commits, never hand-edit `counters.json` /
  `tickets-index.json` / `run.json` — the helper scripts own those.
- Never allocate ticket ids yourself — only `new-ticket.py` mints ids.
- On a resumed run (SKILL.md's Resume & reconcile): redo exactly what the
  reconcile found unfinished; do not rework parts that verifiably hold.

## Grounding (anti-hallucination)

Every decision, claim, and finding you record must be traceable to a source
you actually read or ran in THIS run:

- **Cite the source next to the statement it supports** in the materialize
  report: file path with line numbers or section heading for anything based
  on repo code, docs, the ticket, specs, design, or workspace state.
- **Quote the exact command and the relevant output** for anything based on a
  command run (new-ticket.py, tracker sync, gh state).
- **Never assert what you did not observe**: the content of a file you did not
  open, a remote issue you did not check, a key a command did not print. If an
  input you need is missing or unreadable, record it in `problems` instead of
  working from an assumed version.
- **Mark unverifiable points as assumptions**, with the reason the assumption
  is needed — an assumption is a finding to resolve with the user, never a
  silent default baked into the ticket.
