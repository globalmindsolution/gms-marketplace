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
3. **Design precondition.** Read the epic's design source (its own
   partition's `design.md`, or the `create-design` step in
   `run.json`). When `create-design` has not completed, or
   `design.md` is absent, surface that to the user and obtain their explicit
   confirmation before proceeding — never proceed silently, and never
   hard-refuse; the user may still choose to fan out an undesigned epic.
4. **Breakdown derivation.** When the epic's `design.md` exists, derive the
   proposed child breakdown from the design's own slice/seam content (the
   acs design template's Rollout/migration slice table, when present);
   otherwise derive it from the epic's own description and acceptance
   criteria. Apply Step 1's concreteness/testability judgment to every
   proposed child AC/DoD entry, the same as the root flow.
5. **Confirmation gate.** Reuse Step 2 item 7 — "Epic only: present the
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
   child's `acceptance_criteria` into the child's own `ticket.json` —
   `new-ticket.py` exposes no `--acceptance-criteria` flag.
8. **Sync.** Run Step 5 below, scoped to the newly minted children only —
   see Step 5's sync-set clause for the exclusion rule that keeps the
   epic's own already-synced issue from being re-created.
9. **Finish.** The mandatory Finish below still applies unchanged:
   `result.json` with `states.ticket_id` = the epic, `type: "epic"`,
   `needs_design`, `children` (the epic's full children after this run),
   `prd_trace` (the epic's), then `acs step finish`. Never leave the
   epic's `create-ticket` run non-`completed`: no gate refuses on it any more
   (order lives in `workflows/ship.yaml`), but the ledger is what
   `acs.py run next`, `/acs:metrics` and the derived ticket status read,
   and a run left `in_progress` reports the epic as mid-flight for ever.
