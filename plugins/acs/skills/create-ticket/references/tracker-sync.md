# Tracker sync — /acs:create-ticket Step 5, shared with /acs:breakdown-ticket

Open this ONLY when `settings.tracker.provider` is `github`. On the
default `local` provider there is no remote to sync to and this whole step is
skipped: no issue is created, and every ticket's `external` stays null.

**Two skills follow this one procedure** (ADR-0138, never a copy):
`/acs:create-ticket` syncs the ticket it created (its Step 5), and
`/acs:breakdown-ticket` syncs the children it minted (its Materialize step 5).
"The root ticket" below is the ticket a creation run made, or the parent a
breakdown run cut children from; "the children" are a breakdown run's, and a
creation run has none.

### Step 5 — Tracker sync

Only when `settings.tracker.provider` is `github` (skip entirely for
`local`). Sync is on-demand — this creation run pushes the new ticket(s) out; no
background sync. For `local` (unsynced) tickets, none of this step's github
field-fill behavior fires — no issue is created, so the `acs-ticket:` body line
in the local `ticket.json` description is harmless, already-existing template
content, not new GitHub-facing behavior; this is expected and not a regression
(AC-4).

- Imported tickets: keep `external` as pulled, do NOT create a remote duplicate.
  If local analysis changed title/description AND the remote also changed since the
  pull, report the conflict in the result — ask the user which side wins, then
  re-dispatch.
- **Tickets to sync** = `[root ticket, unless it is an import] + [every child
  a breakdown run minted]`, EXCLUDING any product-flow delivery title
  (`PRODUCT_TICKET_TITLES`: "Product definition (PRD)", "Product architecture
  doc set") — never sync a product-flow ticket (AC-4) — **and EXCLUDING any
  ticket whose `external` is already non-null**: a breakdown run's root
  is already synced, so re-applying this set literally would re-create its
  issue as a duplicate;
  excluding it means only the newly minted children (whose `external` is
  still null) enter the sync set, the same split MAR-69's own fan-out
  produced (issue kept, new issues created for the children only). **For each ticket to
  sync**, run the `gh issue create` sequence below once per ticket — this is
  a **critical (per ticket), soft (per batch)** gh call: a failed `gh`
  call for any one ticket is never silently swallowed: it produces an
  **error**-severity finding naming that ticket's id + error + the canonical
  hint from `acs_lib.gh_failure_hint`, `replayable: false`, surfaced in
  `errors` and the `<handoff>`, and does not abort the batch (the loop continues to other
  tickets; that ticket's `external` stays null). Other tickets are
  unaffected. The Finish report lists which
  tickets synced (with their key) and which failed (with the error) so the
  failed ones can be retried individually. This set covers children minted
  by /acs:breakdown-ticket, an epic's fan-out or a split; a split run's
  already-synced root is excluded by the same `external`-non-null rule above
  and instead has its remote issue **updated** (title/type/links), as
  breakdown-ticket's Materialize step 5 instructs.
- `github` (`tracker.github.owner`, `tracker.github.project_number`): one
  command performs the whole batch — issue creation, labels, assignee,
  milestone, Project membership, and every Project field the board defines:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" tracker sync \
    --ticket SHOP-123 --ticket SHOP-124
  ```

  Pass every ticket in the set above; the command applies the exclusion rules
  itself (a product-flow delivery title, and any ticket whose `external` is
  already non-null — which is what stops a breakdown run re-creating its
  already-synced root as a duplicate). `--dry-run` prints the set it would
  sync and the ids it excluded, and writes nothing. The body it posts is each
  partition's `tracker-body.md`; write that file from the rendered description
  before calling. It is a **precondition**, not an argument: a partition with
  no body is reported under `failed` with an `error` finding naming the
  missing path, and no bodiless issue is created.

  **Read the printed JSON.** `synced` maps a ticket id to its `external`;
  `failed` lists the ids whose `gh issue create` failed. Those are
  **error**-severity findings carrying the ticket id, the error and the
  canonical `gh_failure_hint`, `replayable: false` — surfaced in `errors` and
  the `<handoff>`, never silently swallowed, and **never aborting the batch**:
  the other tickets sync, and a failed one keeps `external` null so it can be
  retried on its own. Every finding carries the `ticket_id` it came from, so a
  batch's flat list stays attributable. Everything after the issue is created
  — labels, assignee, milestone (from `ticket.milestone` only), Projects — is **non-critical**: one `info`
  finding with a replayable, shell-quoted command, never a failed ticket. A board that does not define a
  field (`Type`, `Status`, `Priority`, `Story Points`, `Parent`) is one info
  finding naming exactly what was skipped: a schema-undefined field is
  surfaced, never silently ignored, and never a wrong-type write.


- Write `external` into each synced ticket's own `ticket.json` — root and
  every child — via `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/record-external.py"
  --ticket <ticket-id> --provider <provider> --key <key>` once per successfully
  synced ticket.
