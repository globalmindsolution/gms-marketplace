# /acs:create-ticket — epic fan-out mode (`--fan-out`)

Open this ONLY when `$ARGUMENTS` resolves to a local ticket id AND carries the
`--fan-out` token. This mode creates nothing new: it mints the child
story/task tickets of an EXISTING, already-created epic, after that epic's
design is approved. Every other invocation — a raw request, a remote import,
a split — skips it entirely.

**Where the cross-references below point.** Step numbers (Steps 1-4),
`Resume & reconcile` and `Finish` are SKILL.md's, and a bare "below"
means there, not in this file. Step 5 is
`${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/tracker-sync.md`, and
the split/restructure mode is
`${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/split-ticket.md`.

## Epic fan-out mode (`--fan-out`)

Check this BEFORE the split check below: `$ARGUMENTS` resolves to a local
ticket id AND carries the `--fan-out` token — i.e. this run was invoked as
`/acs:create-ticket <epic-id> --fan-out`. This run does not create anything
new — it mints the child story/task tickets of an EXISTING, already-created
epic, after that epic's own design is approved. Resulting precedence:
`--fan-out` -> split -> remote import -> raw request.

1. **Start.** `acs.py step start --step create-ticket --run <epic-id>` — no
   `--allocate`: the epic's partition already exists, and this invocation is
   recorded as a second `create-ticket` invocation against it (mirroring the
   split mode's Start below).
2. **Type refusal.** When the resolved ticket's `type` is not `epic`, stop
   with a message explaining `--fan-out` applies to epics only — this mode
   mints an epic's children, never a story or task's own children. This
   mirrors, in prose, the refusal `new-ticket.py` already enforces in code
   (`parent %s is a %s, not an epic`), so the two can never disagree.
3. **Design precondition.** Resolve the epic's published design with
   `acs.py artifacts show --ticket <epic-id>` and read
   `artifacts["tech-design.md"]` — the epic's tech design
   `<architecture_dir>/lld/<feature>/<epic-id>/tech-design.md` in the checkout (a
   legacy `design.md` there or in `docs/tickets/<epic-id>/` is still read), or
   the copy in the epic's workspace partition when there was no checkout
   (`null` = none published) — its status (`acs.py design check <path>`), and
   the `create-tech-design` step's status in the epic run's `run.json`. When
   `create-tech-design` has not completed, the tech design is absent, or it is
   not yet `approved` (`/acs:set-doc-status approved <feature>`), surface that
   to the user and obtain their explicit confirmation before proceeding —
   never proceed silently, and never hard-refuse; the user may still choose to
   fan out an undesigned or unapproved epic.
4. **Breakdown derivation.** When the epic's `tech-design.md` exists, derive the
   proposed child breakdown from the design's own slice/seam content. The
   built-in template (`templates/design-default.md`) has no slice table: read
   the seams from its `## LLD` snapshots and `## HLD views affected` (the
   new/changed interfaces, flows, entities and components — each coherent
   change is a candidate child) and the ordering from `## Risks` › `### Rollout
   & migration` (sequencing, migrations, flags, backward compatibility) — plus
   any slice breakdown a repo's own design template adds. A legacy
   `design.md` carries them under `## Architecture` and `## Rollout/migration`. Otherwise derive it from the epic's own
   description and acceptance criteria. Apply Step 1's concreteness/testability judgment to every
   proposed child AC/DoD entry, the same as the root flow.
5. **Confirmation gate.** Reuse Step 2 item 6 — "Epic only: present the
   proposed child breakdown and obtain user confirmation or edits before any
   child is minted" — verbatim; this fan-out run IS that gate's actual
   invocation for an already-created epic. No child is minted before the
   user confirms or edits the breakdown.
6. **Idempotency.** Read the epic's `children` array first; never re-mint a
   child already listed there (see Resume & reconcile, below).
7. **Mint.** For each user-confirmed child, run Step 4 exactly as written
   below. Steps 1-3 do NOT run in this mode — the epic's own `ticket.json`
   (title, description, acceptance criteria, needs_design)
   is not re-analyzed or rewritten; only the epic's `children` array
   changes, via `new-ticket.py`. After minting, write each confirmed
   child's `acceptance_criteria` into the child's ticket with
   `acs.py ticket save`:

   ```bash
   printf '%s' '{"acceptance_criteria": ["...", "..."]}' \
     | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" ticket save --ticket <child-id> --from -
   ```

   `--ticket` names the child; `--from` takes a JSON file, or `-` (or nothing)
   for stdin. The document is a PATCH merged over the stored ticket, so send
   only `acceptance_criteria`. It writes the workspace partition's
   `ticket.json` — the ticket lives only in the workspace and the tracker,
   never in the repo (ADR-0128) — and re-indexes it. Never hand-edit
   `ticket.json`. `new-ticket.py` exposes no `--acceptance-criteria` flag.
8. **Sync.** Run Step 5 below, scoped to the newly minted children only —
   see Step 5's sync-set clause for the exclusion rule that keeps the
   epic's own already-synced issue from being re-created.
9. **Finish.** The mandatory Finish below still applies unchanged:
   `result.json` with `states.ticket_id` = the epic, `type: "epic"`,
   `needs_design`, `children` (the epic's full children after this run),
   `prd_trace` (the epic's), then `acs step finish`. Never leave the
   epic's `create-ticket` run non-`completed`: no gate refuses on it any more
   (order lives in `workflows/ship.yaml`), but the ledger is what
   `acs.py run next` and the derived ticket status read,
   and a run left `in_progress` reports the epic as mid-flight for ever.
