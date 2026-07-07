---
name: test
description: Run this product's configured test suites (all of them, or a --suite-selected subset), capture pass/fail results to an auditable workspace artifact, and (on a failure) triage and drive a closed regression-ticket loop. Use when asked to run the test suites, run a named suite (e.g. "run the e2e suite"), or check whether anything broke — not for reading delivery or usage metrics (see /acs:metrics, /acs:usage).
---

You are the coordinator of `/acs:test`, the acs standing suite runner. This is
NOT a hooked pipeline skill: no skill-start, no pre/post hooks, no subagents,
no reflection loop. You do everything yourself with Bash.

Scope honesty up front: this skill is **not read-only**. Every run **writes**
a results artifact to the workspace (see Step 3), and on a failure path it
**mutates** ticket state (regression tickets minted, commented, or linked) —
this is different from `/acs:metrics`/`/acs:usage`, which are read-only. What
IS shared with those two unhooked utility skills: no skill-start ticket
allocation, no delivery ticket of its own, no subagents, no reflection loop —
`/acs:test` runs its own lightweight start bookkeeping in-skill, exactly like
`/acs:metrics`/`/acs:usage` do.

## Step 1 — Resolve context and arguments

Call `acs_lib.build_context(cwd)` to resolve `settings`, `workspace`, and
`repo_id` exactly as other unhooked skills do. Read
`ctx["settings"].get("suites", {})` — this is the already-resolved suites map
(it carries the normalized `"e2e"` entry automatically when `settings.e2e` is
configured; you never read the raw `e2e` key yourself).

Parse `$ARGUMENTS` for zero or more `--suite <name>` flags:

- **No `--suite` flag:** run every entry in `suites`.
- **One or more `--suite <name>` flags:** run only the named subset, in the
  order given. If a named suite is not a key in `suites`, fail fast with a
  clear error identifying the unknown name(s) — do not silently skip it or
  fall back to running all suites.
- If `suites` resolves to `{}` (nothing configured at all), report that
  plainly ("no suites configured, nothing to run") and stop. There is
  nothing to execute, but you still emit a valid, empty-arrays artifact
  (`suites: [], regressions: []`) per Step 3.

## Step 2 — Per-suite execution: setup → command → teardown

For each suite to run, in order:

- Record a start timestamp.
- If the suite entry has a non-empty `setup` string, run it via the shell
  exactly as configured (same trust boundary as the already-shipped `e2e`
  runner — no new arbitrary-input path).
- Run the suite's `command` string, capturing its exit code and
  stdout/stderr.
- **Always** run `teardown` (if present) — teardown runs even after a
  failing `command`, pass or fail, and its own exit code never overwrites
  the suite's verdict (the verdict is `command`'s exit code only).
- Record an end timestamp; `duration_s` is the elapsed wall-clock time across
  `setup`→`command`→`teardown` combined (the full cost the caller pays per
  suite).
- Suite `status` is `"pass"` when `command`'s exit code is `0`, `"fail"`
  otherwise. `failure_output` is populated only when `status` is `"fail"`
  (captured stdout/stderr from `command`, truncated to a reasonable bound so
  the artifact stays readable and auditable, never multi-megabyte).

**R1 safety — no interpolation.** Never build `setup`, `command`, or
`teardown` by string-interpolating captured failure output, another suite's
exit code, or any other runtime-captured text into a shell command. Each
suite's `setup`/`command`/`teardown` strings come verbatim from
`settings.suites.<name>` as configured — never rewritten, wrapped, or
concatenated with captured data before execution. Captured output is stored
as artifact data only; it is never re-injected as executable input.

## Step 3 — Write the results artifact

After all selected suites have run (or immediately, in the zero-suites case),
write JSON to `<workspace>/<repo_id>/test-runs/<run-id>/results.json`, where
`<workspace>` and `<repo_id>` are exactly what `build_context()` resolved
(the same repo-level directory `acs_lib.repo_dir(workspace, repo_id)`
returns — sibling to `tickets-index.json` and `metrics.json`, NOT inside any
ticket partition, since `/acs:test` is unticketed). `<run-id>` is
`run-<ISO8601>` (an ISO-8601 UTC timestamp with filesystem-path-safe
characters — colons replaced or omitted). Create the `test-runs/<run-id>/`
directory tree as needed.

Artifact shape:

```json
{
  "run_id": "run-<ISO8601>",
  "started_at": "<ISO8601>",
  "ended_at": "<ISO8601>",
  "suites": [
    {
      "name": "<suite-name>",
      "command": "<configured command string>",
      "exit_code": 0,
      "duration_s": 0.0,
      "status": "pass",
      "failure_output": "<only present when status is \"fail\">"
    }
  ],
  "regressions": []
}
```

`regressions` is **always** emitted as an array — this spec's runs always emit
the empty list `[]` (only the failure-path closed loop, layered onto this
same file, ever populates entries into it).

## Step 4 — All-green short-circuit (deterministic guarantee)

After the results artifact is written, check whether every suite that ran has
`status: "pass"`. **If so, stop here.** This is a hard requirement, not a
default that happens to be true today: on an all-green run, **no triage step
runs and no model call of any kind is made** — `regressions` stays the empty
list `[]`. A future edit must not silently introduce a model call on this
branch.

Only when at least one suite's `status` is `"fail"` does control pass to the
failure-path steps below (triage, regression-key derivation, dedup/recurrence,
ticket mint/comment/link).

## Step 4a — Triage (model step, failure path only)

For each suite whose `status` is `"fail"`, read that suite's captured
`failure_output`, `exit_code`, and `command` (from the in-memory run state or
the just-written `results.json` — either is acceptable) and produce:

1. A **regression summary**: one paragraph covering what broke, the likely
   cause, and the first-glance affected component.
2. A **stable regression key** of the form:

   ```
   <suite-name>:<normalized-failing-test-id>
   ```

   where `<suite-name>` is the exact `suites` map key (or the reserved `e2e`
   key) the failure came from, and `<normalized-failing-test-id>` is the
   lowercase, whitespace-collapsed identifier of the single failing test
   parsed out of the suite's failure output.

   **C-1 fallback (binding, not optional):** when the suite's failure output
   yields **no parseable individual failing-test id** — a bare non-zero exit
   code, a compile/build error before any test runs, or any other
   suite-level failure with no per-test identifier to extract — the
   regression key falls back to the **coarse suite-level key**:

   ```
   <suite>:__suite__
   ```

   This is a **literal fixed marker, not a content fingerprint or hash**: a
   suite known to be flaky is a suite-authoring concern, not something this
   closed loop should amplify by minting a new ticket per distinct
   (unparseable) failure blob. The fallback intentionally collapses every
   unparseable failure from the same suite onto **one ticket per broken
   suite**.

Multiple failing suites in the same run each get their own regression key
(and therefore their own dedup/mint/bump decision) — process the
`regressions` candidates one key at a time.

## Step 4b — Dedup / recurrence lookup

For each regression key, search `tickets-index.json`
(`acs_lib.index_path(workspace, repo_id)`, read via `acs_lib.read_json`) for
an existing ticket whose description carries that exact regression-key
marker (see "Regression key marker convention" below) — scanning each
candidate's own `description` field loaded via `acs_lib.load_ticket` at the
partition resolved by `acs_lib.find_ticket_partition(workspace, repo_id,
ticket_id)` (active partition first, then `archive/`).

Given a matching ticket (if any) and its `status`
(`acs_lib.TICKET_STATUSES = ["open", "in_progress", "in_review", "done"]`),
apply this **three-way policy** exactly:

1. **Not found → mint a new ticket.** Invoke `new-ticket.py` (unchanged —
   this skill reuses it as-is, no edits to the file) with `--title "<suite>:
   <test> regression"` (or, under the suite-level fallback, `--title
   "<suite>: suite regression"`), `--type task`, and `--description "..."`
   embedding, in order: the regression-key marker, the triage summary, and a
   link to the results artifact
   (`<workspace>/<repo>/test-runs/<run-id>/results.json`). Record the
   printed `{"ticket_id", "partition"}` and mark this regression's action as
   `"minted"`.

2. **Found, ticket status is `open`, `in_progress`, or `in_review` →
   comment-bump the existing ticket — never mint a duplicate, never silently skip.**
   Append fresh evidence (the new run id, the current timestamp, and
   the latest failure output) to the existing ticket's `description` (loaded
   via `acs_lib.load_ticket`, appended to, saved via `acs_lib.save_ticket`,
   re-indexed via `acs_lib.update_index`). Mark this regression's action as
   `"commented"` with `ticket_id` set to the existing ticket's id.

3. **Found, ticket status is `done` → the regression recurred after being
   marked fixed: mint a NEW ticket linked to the old one — never silently reopen
   the closed ticket.** Call `new-ticket.py` exactly as in case 1, but
   the `--description` additionally states explicitly that this is a
   recurrence and names the old (closed) ticket id it links back to. Mark
   this regression's action as `"minted_linked"` with `linked_ticket_id` set
   to the old ticket's id. The closed ticket itself is left untouched
   (status stays `done`) — reopening it would hide that a shipped fix
   regressed.

**Regression key marker convention.** Every minted/bumped ticket's
`description` embeds the literal marker line:

```
acs-regression-key: <suite>:<normalized-failing-test-id-or-__suite__>
```

on its own line (mirrors the existing `acs-ticket: <ID>` convention already
used elsewhere in ticket descriptions). The dedup lookup searches for this
exact line, not a fuzzy match on summary prose.

**R1 safety — no interpolation (restated for the failure path).** No failure
content (suite output, parsed test ids, triage summary text) is **ever
interpolated into a shell command**. The only commands this step invokes are
in-process reads (`acs_lib.read_json`, `acs_lib.load_ticket`,
`acs_lib.find_ticket_partition`) and one write path — invoking `new-ticket.py`
as a subprocess with `--title`, `--type`, and `--description` passed as
**argument values**, never shell-interpolated into a command string. Failure
output/triage text becomes ticket **description content only**, never a
command or command fragment.

After processing every failing suite's regression key, populate the results
artifact's `regressions[]` array (Step 3's shape) with one entry per
processed key:

```json
{
  "key": "<suite>:<normalized-failing-test-id-or-__suite__>",
  "ticket_id": "<TICKET-ID>",
  "action": "minted" | "commented" | "minted_linked",
  "linked_ticket_id": "<OLD-TICKET-ID>"
}
```

`linked_ticket_id` is present only when `action` is `"minted_linked"`.

## Step 5 — Report

Print a run summary: suites run (count and names), pass/fail counts, and
tickets minted/bumped/linked (on an all-green run, this line is simply "0
tickets minted/bumped/linked" since `regressions` is always `[]` on that
path). State explicitly that the results artifact is left in place on disk
after the run — it is not cleaned up — so `/acs:metrics` can read it later.

## Scheduling surface

`/acs:test` carries no notion of "I am scheduled" versus "I was invoked by a
person" — it is a pure function of "which suites, right now," and the caller
(cron, a CI scheduled workflow, or a Claude Code routine) decides when to
invoke it. See `operations/test-scheduling.md` for the concrete cron/CI/
routine recipe; this skill itself has no built-in scheduler (ADR 0011 G8).

## Completion report (normative)

End your final message with the standard completion block; replace the
Ticket line with **Run** (this skill is run-scoped, not tied to one ticket):

```markdown
## /acs:test · <status>

- **Run**: <run-id>, <N> suites run
- **Status**: <status> — <one line>
- **Results**: <pass count>/<N> suites passed
- **Findings**: <regressions minted/bumped/linked, or "none — all suites passed">
- **Artifacts**: results artifact at test-runs/<run-id>/results.json (left in place)
- **Metrics**: n/a
- **Next**: <e.g. re-run after a fix lands, or schedule a standing run>
```
