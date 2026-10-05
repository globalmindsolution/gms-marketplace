---
name: handoff
description: Hand a ticket over to a teammate on another machine, or pick one up — send packages the ticket's uncommitted work, the run state it resumes from and a handoff note (done, in flight, next, decisions) into the hidden git ref refs/acs/handoff/<ID> on origin, never a branch or a PR; receive restores that work and state into this checkout and prints the command to continue; list shows which ticket handoffs are waiting on the remote. Use when the user wants to hand a ticket, or the work on it, to a teammate, pass it on to someone else, take over or pick up a ticket a teammate handed off, or asks which handoffs are waiting for them. Not for pausing your own session — acs resumes a step from its recorded state by itself. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, run or repo files, and do not look for a shell or git: it locates all of them itself.
argument-hint: "<ticket-id> | receive <ticket-id> | list"
---

You are the coordinator of `/acs:handoff`, the team-handoff utility skill
(ADR-0131): one member hands a ticket to another, across machines, through
the shared git remote. This is NOT a hooked pipeline skill: no `acs step
start`, no pre/post hooks, no subagents, no reflection loop. You do the work
inline with Bash and AskUserQuestion, and every byte that moves is moved by
`acs.py handoff` — never by hand.

**The package.** `acs.py handoff send` builds ONE commit and pushes it to the
hidden ref `refs/acs/handoff/<ID>` on `origin`:

- `work/` — the ticket's uncommitted work, as a snapshot of the working tree
  over the run's baseline (ignored files are never packaged);
- `acs/` — the **resume set**: the ticket, its clarifications, the run ledger,
  the run's requirements and sources, its baseline, and each step's state,
  result, artifacts and verdict. Iteration scratch, jobs, agent copies, locks,
  sessions and logs are never packaged;
- `attachments/` — only the outside-repo files the sender confirmed, one by
  one;
- `note.md` — the handoff note; `manifest.json` — who sent it, when, from which
  base commit and branch.

The ref lives outside every branch: `git log`, `git branch -a` and the PR list
never show it. That commit is the one acs commit that is not
`/acs:create-pr`'s (ADR-0127, amended by ADR-0131), and it is the CLI's job.
You yourself never create or switch a branch, stage, commit, push or open a
PR; `receive` leaves the work as uncommitted changes, exactly as it was on the
sender's machine.

**Not a session pause.** Pausing your OWN work needs no skill: every step
records its state on disk, a step stopped by context pressure finalizes
itself, and `/acs:ship <ID>` resumes the run from its cursor in any session.
When the user only wants to stop and continue later themselves, say so in one
line, give them `/acs:ship <ID>`, and stop — do not send anything.

## Step 1 — Pick the mode

Read `$ARGUMENTS`, then the request's words:

| Arguments / request | Mode |
|---|---|
| `receive <ID>`, or "pick up / take over <ID> from <teammate>" | **receive** (Step 3) |
| `list`, or "what handoffs are waiting (for me)" | **list** (Step 4) |
| `<ID>`, or "hand <ID> to <teammate>", "pass <ID> on to …" | **send** (Step 2) |

A teammate's name is not an argument the CLI takes: on a send it goes into the
note ("For Minh: …"); on a receive it is only who to thank. A receive with no
id runs list first and, when exactly one handoff is waiting, offers it; with
several, ask which (or stop when you cannot ask). A send with no id resolves
the ticket from this checkout's run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" run show
```

Its `run.subject.ticket_id` is the id. When it refuses with `no current run
for this checkout`, there is **nothing to send** from here: say so, suggest
`/acs:handoff <ID>` with an explicit id, push nothing, and finish `completed`.
A run whose `subject.kind` is not `ticket` cannot be handed off — a handoff
names a ticket on both machines: tell the user to give the work a ticket with
`/acs:create-ticket` first, and stop. Never guess an id from the branch name.

## Step 2 — Send

**2a. Preview.** MANDATORY first commands; they push nothing:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" handoff send --ticket <ID> --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" handoff list
```

The dry run prints what the package would hold — `package` (every path in
it: `work/…`, `acs/…`), `work_changes`, the `branch` and `base_sha`,
`excluded` (what stays behind), `left_behind` (files you were already
editing before the ticket's run began — your own work in progress, never sent;
name them in the preview so the sender knows), and `attachments_available`: each
outside-repo document the run copied, by its `ref` and `name`. The list says
whether a handoff of `<ID>` is already waiting on the remote. On a non-zero
exit, surface stderr verbatim and finish `failed` (known cases below).

**2b. Draft the note** from the run, not from memory alone: the ledger's
completed steps (**done**), the step in progress or interrupted and what its
artifacts say is left (**in flight**), the run's cursor —
`acs.py run next --ticket <ID>` — (**next**), and the clarifications ledger
plus anything decided in this conversation that no file records
(**decisions**). Four short sections, a page at most; reference artifacts by
their run-relative path rather than copying them.

**2c. ONE grouped AskUserQuestion**, every question in the same call:

1. **The note** — show the drafted note in the question; options `Send as
   drafted` and free text to replace or extend it.
2. **One question per offered attachment** — `Include` / `Skip`, the
   description naming the file, its size and where the run got it. Nothing
   outside the repo is ever packaged without its own `Include`. More than
   three attachments: one multi-select question listing them all instead,
   every option unchecked by default. An attachment whose `present` is false
   (its copy is gone) is listed under Findings, never offered.
3. **Confirm the push** — the plan in one line: `<n> work files, <n> state
   paths, <n> attachments → origin refs/acs/handoff/<ID>`, and the warning
   that hidden is not private — anyone who can read the remote can fetch the
   package; options `Send`, `Cancel`. When the list showed `<ID>` waiting,
   the options are `Replace the waiting handoff` and `Cancel`: a replace
   overwrites a package nobody has picked up yet.

`Cancel` → status `completed`, "nothing sent", and stop. Ask only what the
request left open: a request that already gave the note's content, said which
attachments to include (or that there are none) and confirmed the push in so
many words has answered all three — skip the ask and send. Without an explicit
confirmation, always ask it: the push is the one step a re-run cannot take
back. A request to replace a waiting handoff counts only when it says so.

**Headless.** When AskUserQuestion is unavailable and the request left any
of the three open, send nothing: print the drafted note, the offered
attachments and the exact `send` command that would run, and finish
`interrupted` with `stop_reason: needs_input`.

**2d. Send.** Write the confirmed note to a temp file outside the repo, then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" handoff send --ticket <ID> \
  --note-file <tmp-note> [--attach <ref> …] [--replace]
```

One `--attach <ref>` per INCLUDED attachment, exactly as
`attachments_available` printed its `ref`; `--replace` only after `Replace
the waiting handoff`. It prints the dry run's report plus `commit`, `pushed`,
`replaced`, `sender` and `withheld_attachments` (the ones you skipped). Never
retry with a `--replace` the user did not choose, and never push the ref
yourself.

**2e. Say what the sender keeps.** Nothing on this machine changes: the work
stays in the working tree, the run, its lock and its state stay as they are.
The package is a copy. If the sender keeps working, a later send with
`--replace` updates the waiting package; once the teammate has received it,
the two copies diverge and the team decides whose continues.

## Step 3 — Receive

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" handoff receive <ID> [--replace] [--keep-ref]
```

In order, refusing before anything is written: it fetches the ref and reads
its manifest, refuses when this workspace already holds the ticket or its run,
refuses a working tree with uncommitted changes (the work arrives as
uncommitted changes and must not mix with yours), and dry-runs a three-way
apply so a checkout whose `HEAD` moved on still takes the work. Then it
applies the work (unstaged, as the sender had it), restores the resume set
into this machine's workspace, raises the id counter, points this checkout at
the run, keeps the commit locally under `refs/acs/received/<ID>`, and deletes
the remote ref unless `--keep-ref`.

- **Dirty working tree** (`the working tree is not clean`) — surface the
  refusal and the files it names; tell the user to commit, stash or move
  them, then run `/acs:handoff receive <ID>` again. Never stash or discard
  anything yourself.
- **This workspace already holds `<ID>`** — ask whether to take the handoff
  anyway (`--replace` moves the local ticket and run to a backup it reports
  under `backup`) or keep the local one; headless → `interrupted`,
  `needs_input`.
- **Conflicts** (`conflicts with this checkout in: …`) — nothing was changed
  and the ref is still on the remote. Report the paths and the CLI's advice
  verbatim; the user reconciles those files or checks out the sender's base,
  then receives again.
- `--keep-ref` only when the user asks to leave the package on the remote as
  well (for a second teammate).

On success show, in order: `sender` and `sent_at`, the **note** verbatim,
`work_changes` (the files now changed in this checkout), `sender_branch` (the
branch the sender worked on — `/acs:create-pr` makes this checkout's branch
when it is time; you never create one), `steps` with their statuses,
`attachments` restored and `withheld_attachments` the sender kept back, and
`continue_with` VERBATIM as the next command (`/acs:ship <ID>`, or the step
to resume, e.g. `/acs:code <ID>`). A `ref_delete_error` is a Finding: the
handoff was received, but the remote ref is still there for someone to
delete.

## Step 4 — List

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" handoff list --details
```

It prints `handoffs: [{ticket, ref, commit, sender, sent_at, branch, note}]`
and `count`. Show one line per waiting handoff — the ticket, who sent it and
when, and the note's first line. `count: 0` → "no handoffs are waiting on
origin". For each, the next command is `/acs:handoff receive <ID>`. List
fetches the packages to read them but changes nothing in this checkout or
the workspace.

## When a command fails

Surface stderr verbatim and finish `failed` (or `interrupted` with
`needs_input` where the user must choose). Known cases:

- `acs requires a git repository`, or no `origin` remote — a handoff travels
  through the shared remote; nothing to do without one. A missing
  `.acs/settings.json` is never the cause: acs runs on its defaults, and no
  `/acs:setup` run is needed first.
- `<ID> is archived (merged or closed) -- there is nothing to hand off` —
  the ticket is done; nothing left to hand over.
- `no ticket <ID> in this workspace` — the id is wrong, or the ticket lives
  on another machine: that machine sends it.
- `a handoff of <ID> is already waiting on origin` — Step 2c's replace
  question; never add `--replace` on your own.
- `--attach <x> is not one of this run's outside-repo attachments` — only
  documents the run already copied can travel; offer the ones listed.
- The push or fetch is refused (no access, offline, a ruleset that blocks
  refs outside `refs/heads/`) — report it; the package was not delivered.
  Never route around it through a branch, another remote or another
  transport.
- `no handoff of <ID> is waiting on origin` — run list and show what is
  waiting.

## Completion report (normative)

Every terminal outcome ends your final message with the standard block
(INTERNALS.md "Completion report"). A handoff runs no loop, so Metrics
carries no iterations. Under list, and on a send with nothing to send, no
ticket is involved: the heading's id is `list` (or `none`) and the **Ticket**
line reads **Scope** — `<n> handoff(s) waiting on origin` or `this checkout`:

```markdown
## /acs:handoff · <ticket-id> · <sent|received|listed> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <completed|failed|interrupted> — <one line; `stop_reason` when interrupted>
- **Results**: send — ref, commit, note sections, attachments included / skipped, and "the sender keeps everything"; receive — sender, note, restored files, steps; list — the waiting tickets
- **Findings**: <refusals and conflicts verbatim, or "none">
- **Artifacts**: send — `origin refs/acs/handoff/<ID>` @ <sha>; receive — the uncommitted repo paths restored and the run directory; list — none
- **Metrics**: <n> work files · <n> state files · <n> attachments · <wall time>
- **Next**: send — tell the teammate to run `/acs:handoff receive <ID>`; receive — the `continue_with` command verbatim; list — `/acs:handoff receive <ID>`
```
