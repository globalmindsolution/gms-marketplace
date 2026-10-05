# 0131 — `/acs:handoff` hands a ticket to a teammate over a hidden ref

**Status**: Accepted · **Date**: 2026-10-05

**Supersedes**: [0003](0003-file-based-state-outside-repo.md) in part — its
consequence that "cross-machine handoff is out of scope (workspace is
machine-local)". The workspace stays machine-local (ADR-0086); what crosses
machines is a package of one ticket's work and state, not the workspace.

**Amends**: [0127](0127-only-create-pr-commits.md) (the handoff snapshot commit
is the one commit an acs skill makes outside `/acs:create-pr`, `/acs:release`
and `/acs:merge-pr`: it is pushed to a hidden ref, never to a branch, and never
merged) and [0129](0129-discovery-design-development-regroup.md) (Utility's
`/acs:handoff` is now a team handoff, member to member, not a session handoff).

## Context

`/acs:handoff` handed a run to a fresh session on the same checkout: flush the
soft context, finalize the in-flight step `interrupted` with `stop_reason:
context_pressure`, release the lock, print the command to continue. ADR-0003
ruled anything wider out because the workspace is machine-local, and ADR-0086
kept it machine-local when it moved it into the main checkout.

A team does not work that way. One member analyses and plans a ticket, another
codes it; a member going on leave passes a half-built ticket on. Today the only
way across is to commit and push the half-done work to a branch — which
ADR-0127 reserves for `/acs:create-pr` — and the run itself (the clarification
ledger, the refined requirements, each step's state, result and verdict) cannot
cross at all, so the receiver starts the ticket's pipeline again.

The same-checkout session handoff, meanwhile, lost its reason to be a skill:
the step skills that run long already flush and finalize themselves under context
pressure (`handoff.py`), and the `PreCompact` hook writes `handoff-context.md`
before the window shrinks. A user who wants to stop can simply stop and re-run
the skill; a resume reads the interrupted invocation either way.

Two handoffs were also being confused. A *phase* handoff — the Design team
finished, Development takes over — is not a transfer of uncommitted state at
all: the designs are approved and merged, and the next team reads them from
the default branch.

## Decision

1. **`/acs:handoff` hands a ticket from one member to another, across
   machines.** It has three modes: `/acs:handoff <ID>` sends, `/acs:handoff
   receive <ID>` receives, `/acs:handoff list` lists the waiting handoffs. The
   deterministic work is `acs.py handoff send|receive|list`
   (`acs_lib/team_handoff.py` and `team_handoff_receive.py`, reusing
   `acs_lib.changes`' snapshot and git helpers); the skill only asks and
   reports.
2. **The transport is a hidden ref, `refs/acs/handoff/<ID>`**, on the repo's
   `origin`. A ref outside `refs/heads/` and `refs/tags/` is not fetched by a
   default clone or fetch, does not appear as a branch, cannot be opened as a
   pull request, and needs no extra service. The package is one commit whose
   parent is the run's `baseline.base_sha` (HEAD when the run has none), built through a temporary index
   (`hash-object -w`, `update-index --cacheinfo`, `write-tree`,
   `commit-tree`), so the sender's HEAD, index, branches and working tree are
   never touched. Send refuses when the ref already exists unless `--replace`,
   which pushes with a lease. `git`, not `gh`, carries it — the same transport
   `/acs:create-pr` pushes with (ADR-0088 governs GitHub API calls).
3. **The package is the resume set**: what a receiver needs to continue the
   ticket where the sender stopped, and nothing a resume does not read.

   | Tree path | Holds | Why |
   |---|---|---|
   | `work/` | the uncommitted work, `acs changes snapshot` (tracked and untracked, ignored files excluded) | the changeset is the working tree (ADR-0127) |
   | `acs/ticket/` | `ticket.json`, `clarifications.json` | the ticket and its answered questions |
   | `acs/run/` | `run.json`, `requirements.md`, `requirements-refined.json`, `baseline.json`, `handoff-context.md`, `subject/sources.json`; per step, the files at the step's root (`state.json`, `result.json`, the current artifacts) plus each `iter-*/verdict.json` | the run ledger every gate, cursor and resume reads |
   | `attachments/` | the outside-repo documents the sender confirmed, one by one | a run's `subject/` copies may be private; nothing leaves the machine unconfirmed |
   | `note.md` | the sender's note: done, in flight, next, decisions not yet in a file | the soft context a session handoff used to flush |
   | `manifest.json` | format, ticket, sender, time, base, branch, the withheld attachments, the sender's `counters.next` (`schemas/handoff-manifest.schema.json`) | the receiver checks it before writing anything |
   | `trees/<sha>` | every tree the state cites (`baseline.tree`, a verdict's `reviewed_sha`) | so `acs changes diff --since` resolves on the receiver |

   Absolute paths inside the resume set travel as tokens (`${ACS_RUN_DIR}`,
   `${ACS_REPO_DIR}`, `${ACS_CHECKOUT}`) and are rewritten to the receiver's
   own paths. **Left out**: the `iter-*/` audit trails except their
   verdicts, a step's sub-directories, `jobs/`, `agents/`, `lock.json`,
   `lock-events.jsonl`, `sessions/` pointers and logs — machine-local,
   per-session or history a resume never reads — and every outside-repo
   attachment the sender did not confirm. `send --dry-run` reports the
   package and the attachments and pushes nothing.
4. **The sender keeps everything.** A successful send changes nothing local:
   the work stays in the tree, the run, its steps and its lock stay as they
   were. A handoff is a copy, not a move; the sender decides when to discard.
5. **The receiver applies with a three-way merge, from a clean tree.** `receive`
   fetches the ref and validates its manifest, refuses a local run or ticket
   with the same id unless `--replace` (which moves them under
   `handoff-backups/<ID>-<stamp>/` first), refuses a dirty working tree, and
   dry-runs `git diff --binary <base> <work>` through `git apply --3way` in a
   temporary index — so a receiver whose HEAD has moved on still applies, and
   a conflict is reported with its paths while the checkout is untouched.
   Then it applies for real (the changes land unstaged, as the sender had
   them), restores the resume set with this machine's paths, upserts
   `tickets-index` and `runs-index`, raises `counters.next` to at least the
   sender's and points this checkout at the run. It prints `continue_with` —
   the interrupted or in-progress step's skill, else the run's cursor, else
   `/acs:ship <ID>`.
6. **The ref is deleted on receive**, unless `--keep-ref`; the receiver keeps
   the commit locally under `refs/acs/received/<ID>`, so the trees the state
   cites stay reachable. `list` reads `git ls-remote <remote>
   'refs/acs/handoff/*'` (`--details` fetches each for its sender, time and
   note). The remote is `origin` unless `--remote` names another.
7. **A phase handoff needs no skill.** The finishing team approves its
   documents with `/acs:set-doc-status` (ADR-0130), opens the docs PR with
   `/acs:create-pr`, and tells the next team; the next team starts from the
   merged documents. Only a ticket in mid-flight needs `/acs:handoff`.
8. **The internal context-pressure pause is unchanged.** `handoff.py`
   (finalize `interrupted` with `stop_reason: context_pressure`, release the
   lock, print `continue_with`) and the `PreCompact` hook's
   `handoff-context.md` stay as they are, under their names, and the skills
   that call them keep calling them. The documentation calls this the
   **session pause**; only the user-facing session-handoff skill is gone.

## Consequences

- A ticket crosses machines with its work and its pipeline state, so a
  receiver continues at the step the sender stopped at instead of re-running
  analysis and planning, and nothing reaches a branch before `/acs:create-pr`.
- A receive never resets, cleans, stashes or writes the real index: the 3-way
  merge runs as `git apply --3way --cached` in a temporary index, only the paths
  that differ are written to the tree, and a conflict changes nothing. That needs
  git 2.34 or newer on the receiving machine; an older git fails with git's own
  error and nothing is touched.
- **Anyone with read access to the remote can fetch the ref.** Hidden is not
  private: `git fetch origin refs/acs/handoff/<ID>` works for every reader.
  The package carries the work, the requirements, the clarification answers and
  any confirmed attachment — send only what the repo's readers may see.
  Deleting the ref does not purge its objects at once; a host may keep them
  reachable by id until it garbage-collects.
- **Size.** The package holds every uncommitted file in full plus the step
  artifacts; a large binary in the working tree goes with it. Pushing it needs
  write access, and a ruleset that restricts ref creation outside
  `refs/heads/` refuses it — the push error is reported as is.
- **A receiver must start from a clean tree.** `receive` refuses otherwise:
  mixing a teammate's work into one's own uncommitted changes would make the
  run's changeset (ADR-0127) unattributable.
- Two copies of the run exist after a send. If both members keep working, they
  diverge; there is no merge of runs. A re-send needs `--replace`, and a
  receiver who already took the earlier one needs `receive --replace`.
- The session-handoff phrasings ("hand off", "continue this in a new session")
  no longer route to `/acs:handoff`; a long session is paused by the skill
  itself or simply re-run. The skill count stays 29 and `/acs:handoff` stays
  unhooked.
