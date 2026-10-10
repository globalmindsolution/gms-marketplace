# /acs:create-ticket — materializing the confirmed ticket (Steps 3-5)

Open this once Step 2's user-confirmation gate has closed, and follow it
yourself, inline. Materializing a ticket is a fixed sequence of commands
(rewrite `ticket.json`, sync the tracker) with nothing for a separate agent to
judge: the draft was already judged by the reviewer and confirmed by the user, so
the coordinator that ran the confirmation runs this too. The confirmed decisions
are binding here: you do not re-analyze or re-decide while materializing. If the
confirmed draft turns out impossible to write as confirmed, stop and say so (the
Finish failure path in SKILL.md); never improvise.

**Where the cross-references below point.** Step numbers (Steps 1-5),
`Resume & reconcile`, `User interaction` and `Finish` are SKILL.md's. Step 5's
full text is `${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/tracker-sync.md`.
Minting an epic's children is `/acs:breakdown-ticket`'s, never this sequence's.

## What you work from

Everything below reads workspace state and the confirmed decisions, never a
paraphrase of them. Before writing anything, re-read:

- `<partition>/ticket.json` — its parent directory IS the partition;
- the last reviewed draft, `steps/create-ticket/iter-<n>/draft.json` (and
  `draft.md`), with the user's Step 2 revisions applied, plus the clarification
  ledger (`clarify.py list`);
- the settings you need: `tracker_provider` (`local`|`github`) and whether
  tracker sync is on;
- the confirmed decisions: the final type, `docs_only`,
  the due date, the confirmed PRD link (features and requirements), and any
  conflict resolutions.

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

1. **Check the title**: an epic's title is prefixed `[EPIC] `; a story's, a
   task's and a bug's is the title as given. The author set it; correct it only
   when the user's confirmation changed it.
2. **Check the description**: the author built it from the type's template
   (`${CLAUDE_PLUGIN_ROOT}/templates/<name>.md` — `epic-default`,
   `story-default`, `task-default`, `bug-default`; a repo's own
   `<repo>/.acs/templates/<name>.md` of the same name replaces it) with every
   section filled and the HTML comments deleted — except the `## References`
   marker pair. Apply the user's confirmed revisions to it so the description
   and `acceptance_criteria` agree.

   **The `## References` section is required** (ADR-0140): the heading with its
   `<!-- acs:references -->` and `<!-- /acs:references -->` markers and nothing
   you wrote between them, before `## Notes`. Missing — a repo template older
   than this, or a draft that dropped it — add it back there, empty; filled by
   hand — empty it. Code fills it (step 3b, and the tracker in step 5).

   Every description template carries an `acs-ticket: {ticket_id}` line in
   its `## Notes` section — the rendered text is byte-identical across the
   built-in templates, so the acs ticket id is visibly recorded in the
   ticket's own body regardless of type (AC-1). It renders unconditionally —
   it is NOT itself conditional on tracker sync; what IS conditional is
   whether that description ever reaches GitHub (Step 5, skipped on the
   `local` provider, AC-4).
3. **Rewrite `<partition>/ticket.json`** through `acs.py ticket save --ticket <id> --from -`
   (the whole document on stdin as a `<<'ACS_EOF'` heredoc, never the Write tool),
   PRESERVING `id`, `status`, and
   `created_at`, and setting every field required by
   `${CLAUDE_PLUGIN_ROOT}/schemas/ticket.schema.json`: `title`, `type`,
   `description`, `acceptance_criteria` (array of testable strings),
   `priority` (`critical|high|medium|low`), `parent` (null — this skill
   creates roots), `children` (`[]` on every creation run, including an
   epic's own — `/acs:breakdown-ticket` fills it later; the retired Step 4
   `--fan-out` never runs here), `external` (the
   import mapping, the step-5 sync result, or null), `assignee` (or null),
   `story_points` (or null), `docs_only` (the confirmed value,
   default false), `due_date` (ISO-8601 date string or null), `features`
   (the confirmed PRD feature slugs — at least one for an epic, a story or a bug; omit
   for an unlinked technical task), `requirements` (the confirmed
   `<slug>/R<n>` ids; omit when none — `ticket save` refuses one the feature's PRD
   does not declare, and the post-hook refuses a story with none, ADR-0144), and on a bug its
   `severity`, `reproduction`, `expected`, `actual` and `environment`
   (strings); refresh `updated_at` (ISO-8601 UTC). Send ONLY ticket fields:
   the draft's `prd_trace`, `flags`, `open_questions`, `assumptions` and an
   epic's `breakdown_outline` are not ticket fields — `prd_trace` goes to the
   result document, the rest to the materialize report.
3b. **Record the ticket's references** — every document the standard layout
   holds for its features (the PRD section, the feature analysis, the HLD and
   LLD views, design records, development docs), stored on the ticket:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" ticket references --ticket <id> --write
   ```

   Read the printed `references` back for the completion report (published
   entries with their link, the rest `pending: not on <default> yet`). An empty
   list is fine (no PRD, no feature docs yet): it is recorded, not an error.
4. **No children.** A creation run mints none, an epic's included. Its
   breakdown outline stays in the description's `## Notes`, for
   `/acs:breakdown-ticket <id>` to read.
   An epic ends with `children: []`; `/acs:breakdown-ticket <id>` (after
   `/acs:create-tech-design <id>` when the user wants a design first)
   proposes its children in one confirmation,
   mints them with `new-ticket.py --parent`, and syncs them. The same skill
   splits an oversized story or task into an epic that keeps its id.
5. **Tracker sync** — only when `settings.tracker.provider` is `github`;
   skip entirely for `local`.
   - **The "tickets to sync" set:** `[the ticket, unless it is an import]`,
     EXCLUDING a product-flow delivery title (`PRODUCT_TICKET_TITLES`:
     "Product definition (PRD)", "Product architecture doc set") — those are
     never synced by this skill (AC-4) — **and EXCLUDING any ticket whose
     `external` is already non-null** (an import, or a resumed run that already
     synced it): re-creating its issue would be a duplicate.
   - Imported tickets: keep `external` as pulled; NEVER create a remote
     duplicate. The issue already exists, so give it its `## References`
     section with `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" tracker
     refresh --ticket <id>` instead of a sync — **non-critical**: a failure is
     one `info` finding with the replayable command, never a failed run. If your local title/description changed AND the remote also
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
       the ticket's rendered description, for every ticket in the batch; the
       command fills its `## References` block with fresh links (it fetches
       `origin/<default>` first) before the issue is created. The
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
   - Write `external` into the synced ticket's own `ticket.json` via `python3
     "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/record-external.py" --ticket
     <ticket-id> --provider <provider> --key <key> --url <url>` (the `key` and
     `url` of its `synced` entry) once per successfully synced ticket. A failed `gh` call for any one ticket in the set
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
   `steps/create-ticket/iter-<n>/materialize.json` through `acs.py write` (SKILL.md's Finish): artifacts
   produced, files changed, commands run with outcomes, problems hit, and the
   confirmed decisions you applied.

## The materialize report

`iter-<n>/materialize.json` is the audit record of what steps 1-5 did; the
result document (SKILL.md's Finish) summarizes it and never inlines its
detail. A creation run mints no children, so it carries no `children`
finding — `children` stays `[]`:

```json
{
  "status": "completed",
  "files_changed": [
    "/abs/path/to/partition/ticket.json"
  ],
  "commands": [
    {"cmd": "python3 .../acs.py ticket save --ticket SHOP-123 --from -", "outcome": "saved bug SHOP-123"}
  ],
  "findings": [
    {"severity": "info", "dimension": "external", "detail": "synced as github 789"}
  ],
  "decisions_applied": ["type bug (C-1)", "severity high, priority medium (C-2)", "draft iter-2 confirmed"],
  "problems": []
}
```

- `files_changed` lists every file you wrote or changed (workspace state — no
  ticket file enters the repo).
- `status: "failed"` with `problems` when a step cannot complete (keep what
  you finished), then take SKILL.md's Finish failure path; the only question
  this sequence ever raises is the sync-conflict case above.

## Hard rules

- Spawn no subagent for any of this: the steps above are ordered commands the
  coordinator runs itself (the authors and the reviewer ran before Step 2).
- Mutate ONLY what the confirmed draft covers: the ticket partition (through
  `acs.py ticket save`) and the remote tracker. Never touch consumer-repo
  source, never create branches/commits, never mint a child, never hand-edit
  `counters.json` / `tickets-index.json` / `run.json` — the helper scripts own
  those.
- Never allocate ticket ids yourself — `step start --allocate` minted this one.
- On a resumed run (SKILL.md's Resume & reconcile): redo exactly what the
  reconcile found unfinished; do not rework parts that verifiably hold.

## Grounding (anti-hallucination)

Every decision, claim, and finding you record must be traceable to a source
you actually read or ran in THIS run:

- **Cite the source next to the statement it supports** in the materialize
  report: file path with line numbers or section heading for anything based
  on repo code, docs, the ticket, specs, design, or workspace state.
- **Quote the exact command and the relevant output** for anything based on a
  command run (ticket save, tracker sync, gh state).
- **Never assert what you did not observe**: the content of a file you did not
  open, a remote issue you did not check, a key a command did not print. If an
  input you need is missing or unreadable, record it in `problems` instead of
  working from an assumed version.
- **Mark unverifiable points as assumptions**, with the reason the assumption
  is needed — an assumption is a finding to resolve with the user, never a
  silent default baked into the ticket.
