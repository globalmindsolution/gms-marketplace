---
name: create-pr
description: Commit, push and open (or update) the pull request — the one acs skill that branches, commits and pushes. It splits the working tree's uncommitted changes into small reviewable commits (documents by doc set, then each slice's tests then code, doc updates, e2e suites), previews that plan for the user to confirm, commits it on a new branch, pushes, and opens the PR against the default branch with the ACS label, title and body composed from workspace state. Takes a ticket id, documents, a prompt, a mix of them, or nothing (this checkout's current run); no ticket is needed — a PRD, architecture, LLD or ADR change or a prompt-driven fix ships the same way. Use whenever work in the working tree is ready for human review; the gate is a safety brake, not an order check — it refuses only a run whose recorded review left the verifier failing. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, plan, run or repo files, and do not look for a shell or run git yourself: it locates all of them itself.
argument-hint: "[ticket-id] [documents…] [prompt]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-pr. Your job: turn the work in the
working tree into a pull request. This is the ONLY acs skill that creates a
branch, stages, commits or pushes (ADR-0127): every pipeline step before it
leaves its output as uncommitted changes and records the paths it wrote, and
you split those changes into small reviewable commits the user confirms, push
them, and open the PR. Everything in the PR — title, body, ticket reference,
change list, test plan — is composed from WORKSPACE STATE (the run's
requirements, the ticket when there is one, `specs/`, `tech-design.md`, `steps/code/state.json` including its review summary,
the confirmed commit plan), never from conversation history. You perform all of
the apply-work yourself, inline, following `references/publish.md`, and
**spawn no subagent** — no planner, no executor, no verifier: committing a
confirmed plan, pushing a branch and opening a PR is a fixed sequence of
commands with nothing for a separate agent to judge; the one judgment, how the
changes split into commits, is the user's. You persist every phase artifact to
the run's `steps/create-pr/`, and finish by writing the result document and
running the post-hook — always, even on failure.

## What it ships: a ticket, a prompt, or the current run

No acs skill needs a ticket: each takes a ticket id, documents, a prompt or a
mix of them, and so does this one.

| Invocation | Run | Changeset the plan splits |
|---|---|---|
| `/acs:create-pr <ticket-id>` | that ticket's run | what changed since the ticket's first step recorded its baseline |
| `/acs:create-pr` (no argument) | this checkout's current run — ticket- or prompt-subject (e.g. after `/acs:code "fix the login timeout"`) | what changed since that run's baseline |
| `/acs:create-pr "<prompt>"` with no current run | a new prompt-subject run | every uncommitted change against HEAD |

The flow is the same for all three. Where the run has no ticket, the steps say
what changes: no ticket id in commit subjects, no ticket reference or tracker
sync in the PR, and `/acs:merge-pr --pr <number>` to land it.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-pr --args "$ARGUMENTS"
```

If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
improvise a workaround.

The pre-hook is a SAFETY BRAKE, not an order check, and it applies only when
the run has a code step: it refuses when that run HAS a review whose verifier
did not pass (`states.verifier_passed != true`) — a failed review loop must
never reach a reviewer. It does NOT require that `/acs:code` or
`/acs:docs-sync` completed: order lives in `workflows/ship.yaml`, so a run
with no code step at all — documents only, say — passes the gate (running out
of that declared order just earns ONE advisory line on stderr). So do not
assume a code run exists: read `steps/code/state.json` and treat a missing
file as "no recorded implementation" — see "State inputs" below.

Parse the printed context JSON. Fields you will use:

- `run_id`, `subject` — the run and what it is about (`kind` `ticket` or
  `prompt`; a prompt subject carries its text).
- `requirements` — `{path, sources, acceptance_criteria, features, feature}`. **Requirements: `context.requirements` / `acs.py requirements
  show` — a ticket id, documents and a prompt are only where they came from;
  never read ticket.json for acceptance criteria.** The body's acceptance
  criteria and test plan come from `requirements.path`.
- `ticket_id`, `ticket` — id, title, type, and `external` (the
  `{provider, key}` remote-tracker mapping, when synced). Absent when the run
  has no ticket: then there is no ticket reference, no tracker sync and no
  ticket status move.
- `partition` — absolute path of the run's directory; phase artifacts go in
  its `steps/create-pr/`.
- The PR title is free text you write (concise, normally the ticket's title,
  else a summary of the prompt); no script renders it, and the body's Ticket
  section names the ticket when there is one. The
  body template is the built-in `pr-default` (a repo's
  `.acs/templates/pr-default.md` replaces it).
- `settings.tracker` — `provider` is `local` (no sync) or `github`.
- `settings.ticket_prefix` — for the pre-open self-check.
- `checkout_root`, `plugin_root` — for template resolution.
- `reconcile`, `handoff_summary`, `prior_status` — see
  `references/resume.md`.
- `design` — `{exists, dir, source}`: the tech design found for the run —
  its own (`source` `"own"`), else its parent epic's (`"parent"`). `design.dir`
  is the folder the found file is in (normally
  `<architecture_dir>/lld/<feature>/<id>/`, or a kept-local copy). When
  `design.exists`, the tech design there — `tech-design.md`, else a legacy
  `design.md` — feeds the Summary/Changes content. Call it `<design_doc>`.

State inputs (read these; conversation history is NOT an input):

- the run's `requirements.md` (`requirements.path`) — title, description,
  acceptance criteria, whatever container they came from; and the ticket
  (`context.ticket`), when there is one — type and `external` mapping.
- `steps/code/state.json` — `invocations[-1].states`: `specs_implemented`,
  `tests` `{passed, failed, coverage_percent, coverage_target}`,
  `docs_updated`, `files`, `review` `{iterations, findings_open}` (plus
  `guard_denials`, derived, only when the file-map guard denied a write during
  the /acs:code run — read it if you report it, never write or gate on it:
  this skill's gate stays `verifier_passed` and the body's review tick stays
  `review.findings_open == 0`).
- `<partition>/specs/*.md` — scope and API/data changes per spec.
- `<design_doc>` — the decision, when `design.exists`.
- The commit plan `acs.py pr plan-commits` prints (step C1) — built from what
  every step recorded (`states.files`, the analysis publish record, the
  implementers' reports, docs-sync's and create-e2e-tests' files — other
  runs' recorded files too, where they name a changed path) intersected with
  the run's working-tree changeset.

## The references, and when to open each

Nearly all of this skill is one flow: plan the commits, confirm them, commit,
push, write the title and body, open the PR, record it. Two parts are not, and
each row below is read by exactly one kind of run:

| Open | When |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/skills/create-pr/references/resume.md` | `context.reconcile` or `context.handoff_summary` is set. It carries the reconcile procedure: a partially executed commit plan resumes from its first uncommitted group, and a PR may already exist for the branch. A fresh run skips it. |
| `${CLAUDE_PLUGIN_ROOT}/skills/create-pr/references/ci-convention-check.md` | The "Branch / PR / commit conventions" check reports failing after the PR is open. It carries the frozen-payload rule: a red run may be stale, a rerun replays the same stale payload, and an unverified check is never assumed green. |

## Inline apply flow

No planner-executor-verifier triad. No planner or verifier subagents are
spawned for this skill. This inline flow holds on every delivery path —
`trivial`, `small`, `standard`, `complex`, a run with none recorded, and a
run with no ticket — because create-pr runs after the work is written and the path it
took is not an input here. No path re-introduces a planner or verifier for
create-pr.

**Verifier-gated upstream (AC-5).** Correctness is gated by the upstream
review (/acs:review-code's verdict, from which the post-hook derives
`verifier_passed`). The pre-hook enforces that as a brake — a recorded review
with `states.verifier_passed != true` is refused — rather than as a
precondition that a code run exist at all. The human checkpoints are the
commit preview and the PR review. /acs:create-pr carries no in-skill
verifier; invariant (d) lives in the upstream code/spec lanes, not in
apply-work.

**No subagent is spawned — you run the numbered steps inline.** The
coordinator performs every step below itself, in order; it never delegates
them to any subagent, on any delivery path or iteration. Open
`${CLAUDE_PLUGIN_ROOT}/skills/create-pr/references/publish.md` before step C1
and follow it alongside these steps: it carries the ordering and safety rules
that bind them (what may be mutated, what may be committed, no force-push, no
fabricated body content), how each outcome ends the run, and the publish
report's shape. There is no `<task>`/`<result>` exchange and no subagent model
to configure.

### Commit phase — local, no forge call

The working tree's changes become commits before anything touches origin. This
phase needs no `gh`: a forge that cannot be reached never costs the user their
confirmed commits, and a re-run resumes at the push.

C1. **Plan.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" pr plan-commits \
     --out <partition>/steps/create-pr/iter-<n>/commit-plan.json
   ```

   It plans for this run, whatever its subject (`<partition>` and `<n>`, the
   `iteration`, come from the context JSON). It prints `{"branch", "base", "groups": [{"id", "subject", "layer", "paths"}],
   "left_out", "excluded"}` and writes the same plan to `--out`: the proposed
   branch (the current one when it already is a feature branch), the baseline
   commit, the ordered groups — documents first, one group per doc set (ticket
   docs, PRD, `hld/`, each `lld/<feature>/`, ADRs), then per plan slice its
   tests then its code (a run with no plan: its tests, then its code), then
   the doc updates, then the e2e suites — the paths changed that no step
   recorded (`left_out`), and the paths already dirty before the run began
   (`excluded`). It is deterministic; never hand-build a plan or run
   `git status` to make one.

   - A non-zero exit is the answer: surface its message and stop failed.
   - **No groups** (nothing left to commit — the work is already committed,
     pushed or not): skip C2–C3 and run C4 only to cut the plan's branch at
     HEAD when you are not on it (detached HEAD, or the default branch with
     commits ahead of origin). `ahead` is the plan's list of commits HEAD
     carries that the default branch does not, `pushed` whether origin has the
     branch at HEAD; the publish phase skips the push when `pushed` is true.
     No groups and no `ahead` means there is nothing to ship — say so and stop
     failed. Uncommitted changes beside `ahead` commits are planned as usual;
     the PR carries both.

C2. **Preview and confirm — ONE grouped question.** Show the user the whole
   plan in one AskUserQuestion: the branch, then each group in order as its
   subject and its paths, then the `left_out` list (changed, recorded by no
   step — they stay uncommitted unless the user moves one into a group), then
   the `excluded` list (dirty before the run — never committed by this run).
   The choices are **confirm**, **edit**, **cancel**:

   - **confirm** — commit the plan as shown.
   - **edit** — the user moves a path between groups, drops a path from a
     group (it stays uncommitted), adds a `left_out` path to a group, or
     rewords a subject (with a ticket it keeps the configured commit-subject
     format, `{ticket_id} {summary}`; without one the subject is the summary
     alone). Apply exactly those edits to the plan and show
     the edited plan once more for confirmation; never add a path the user did
     not name, and never an `excluded` one.
   - **cancel** — commit nothing, push nothing; finish `interrupted` /
     `needs_input` with "cancelled at the commit preview" in `summary`.

   Record the answer (`clarify.py add --skill create-pr --question "Commit
   plan" --answer "<confirm | the edits | cancel>"`) BEFORE acting on it. When
   the request itself already approves the proposed plan as is ("commit it the
   way you split it"), that IS the answer: record it with `--source user`, show
   the preview in your reply, and proceed. Silence is not approval: a run that
   cannot reach the user and holds no such approval commits nothing and hands
   off `needs_input` (see "User interaction").

C3. **Keep the confirmed plan** in `steps/create-pr/iter-<n>/commit-plan.json`:
   `--out` already wrote it as proposed; after an edit, rewrite it whole through
   `acs.py write` (as in Finish) as that plan with the user's edits applied, nothing
   else changed.

C4. **Commit.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" pr commit --plan steps/create-pr/iter-<n>/commit-plan.json
   ```

   It creates the plan's branch from the current checkout when you are not
   already on it (`git switch -c` carries the working tree with it), then
   commits each group in order by pathspec, and prints `{"branch", "commits":
   [{"id", "subject", "sha", "paths"}], "remaining"}` — `remaining` is what
   stays uncommitted. It refuses the default branch, a branch that already
   exists at another commit, a path that is not an uncommitted change, a path
   in two groups, and an empty group: surface the refusal and stop failed —
   never work around it with a raw `git add` / `git commit`. A refusal midway
   names the commits made so far; record them. Copy the printed commits into
   the publish report and `states.commits`.
   Paths the plan left out stay exactly as they were in the working tree.

### Publish phase — origin and GitHub

1. **Branch and base.** The branch is the one C4 committed to (or C1 named).
   Detect the base branch here, BEFORE anything is pushed:
   `gh api repos/{owner}/{repo} --jq .default_branch`. That call
   is **critical**, so its failure now stops the run before the push instead of
   after it; step 2 reuses the `<base>` it yields rather than detecting it
   again. The commits C4 made stay on the local branch; a re-run resumes at
   the push.

   **One message for the independent calls.** None of these depends on
   another or on the push, so issue them as parallel Bash calls in ONE
   message: the base detect above, step 3's label create, and step 5's
   open-PR detect (`references/rest-transport.md`, "Detect" — a PR can only exist for a branch already
   on origin, so the answer is the same before the push). Steps 3 and 5 reuse
   those results rather than running the calls again. A failed critical call
   among them stops the run before the push, as above.

   Then push: `git push -u origin <branch>`. If the branch is already on
   origin and current, skip the push. Never force-push, never push the default
   branch.

2. **Body.** Resolve the body template: the built-in `pr-default`
   (`${CLAUDE_PLUGIN_ROOT}/templates/pr-default.md`), or the repo's own
   `<checkout_root>/.acs/templates/pr-default.md` when it has one.
   Unresolvable template = blocking problem, surface it. Fill the resolved
   template into `steps/create-pr/pr-body.md` through `acs.py write` (as in Finish):
   replace every placeholder (`{ticket_id}`, `{type}`, `{title}`, `{summary}`,
   `{external_key}`; `{external_key_line}` renders as
   ` — tracker: <provider> <key>` when `ticket.external` is set, empty
   otherwise), replace HTML comments with real content and DELETE the comments,
   fill every section strictly from the state files (`requirements.md`,
   `ticket.json` when there is a ticket, `steps/code/state.json`, `specs/*.md`, `tech-design.md` when required, the
   confirmed commit plan). The base branch is the repo's default — the `<base>`
   step 1 already detected; reuse that value rather than running the detect a
   second time.
   Write the PR title directly — concise, normally the ticket's title
   (`ticket.json` `title`; with no ticket, a summary of the requirements — the
   prompt or the documents — or of the doc sets changed); no script renders it. This is the exact value passed **verbatim** as the `title` of step 5's create/update — no further transformation. The ticket is
   named by the body's Ticket section, not the title.
   Body: Summary (from specs scope + design decision), Ticket (id, title,
   type, external key), Changes (the plan's `ahead` commits and the commits made, in order — one bullet per
   commit: short sha, subject, the paths it carries — plus `specs_implemented`
   and `docs_updated`), Test plan (from
   `tests.passed/failed/coverage_percent/coverage_target` and the specs' test
   plans), Checklist (tick exactly what code-state evidences — e.g. `[x]`
   only when `review.findings_open == 0`).

   **No ticket.** The Ticket section says "No ticket — <the run's prompt>",
   with no ticket id and no `Closes #` line; Summary comes from the prompt and
   the changed files (a documents-only change: their headings); Test plan and
   Checklist tick only what the run's own state evidences. The PR carries the
   `acs-exempt` label (step 3): the installed CI check
   (`templates/ci/acs-conventions.yml`) still fails any PR whose description
   names no ticket, and that label is its fixed exemption.

   **GitHub-native issue link (AC-2, AC-7).** When
   `ticket.external.provider == "github"` AND `ticket.external.key` is set,
   `pr-default.md`'s `## Ticket` section renders a `Closes #{external_key}`
   bullet — a distinct bullet from the existing `{external_key_line}`
   (` — tracker: <provider> <key>`) — so GitHub's issue-closing keyword parser
   recognizes it as its own line/bullet. When `ticket.external` is null/local
   or the provider is not `github` (the unsynced case), the bullet is omitted
   entirely, not rendered blank — the rest of the body renders byte-identical
   to today (AC-4, no regression for `local`/unsynced tickets).

3. **Label.** `gh label create ACS --description "Created by the acs pipeline" 2>/dev/null || true`
   (already issued in step 1's batch) — this label plus the `Closes #{external_key}` linking line together make
   the PR independently identifiable and traceable without depending on the
   local acs ticket id being unique across contributors (AC-7). A run with no
   ticket also ensures `acs-exempt` the same way and applies both labels at
   step 5.

4. **Pre-open self-check.** Before either branch of step 5 creates or
   updates the PR, self-check the filled body against exactly what CI
   will check, with the helper's `check` subcommand — a deterministic CLI
   call, never a spawned subagent and never a plan/execute/verify triad — no
   new subagent role is introduced by this step:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pr-conventions.py" check \
     --body-file steps/create-pr/pr-body.md --ticket-prefix <settings.ticket_prefix>
   ```

   CI checks one thing (ADR-0106): the description names its ticket — the id
   (`<prefix>-<n>`), a `#<n>` reference or an issue link. `check` runs
   `check-conventions.py`'s own rule rather than a copy of it, which is what
   keeps the self-check and CI enforcement from drifting, and adds two
   hygiene scans: an unrendered `{placeholder}` and a leftover `<!-- -->`
   comment. The title and the `ACS` label are how acs writes the PR, not
   rules CI checks, so neither is self-checked. With no ticket a `ticket_link`
   error is expected — the `acs-exempt` label is what CI honours — and only
   the two hygiene scans must pass.

   - **On pass** (exit 0 / `passed: true`): proceed to step 5 unchanged.
   - **On failure** (exit 1 / `passed: false`): this reports structured
     findings from a deterministic call. Perform a bounded local retry: if
     the failing heading is `ticket_link`, re-fill the Ticket section so the
     body names the ticket id; if it is `unrendered_placeholder` or
     `leftover_template_comment`, delete the surviving placeholder/HTML
     comment in `pr-body.md` (rewrite it whole through `acs.py write`), then re-run
     `check`. Cap the retry at a small bounded number of attempts (up to 2 re-fills) — this is a tight
     fix-and-recheck loop around one deterministic call, NOT a new
     plan/execute/verify iteration. If `check` still fails after the bounded
     retries, STOP: do NOT create or update the PR; surface a
     blocking problem naming the exact failing heading(s)/detail(s) from the
     helper's `errors`, write it into the phase artifact, and follow the
     Finish failure path — `states.pr` is omitted if no PR exists yet, or kept
     as the last-known-good object if updating an existing PR that could not
     be re-validated. Never open or leave in place a PR known to be
     non-conforming as a result of this run.
   - Apply this identical self-check on BOTH the create path and the edit
     path below — one `check` call before whichever call ends up
     running.

5. **Create or update PR.** Detect existing open PR — step 1's batch already
   ran the REST detect (`references/rest-transport.md`); use its answer. If no open PR exists for the branch:

   `references/rest-transport.md` lists REST calls that work with `gh`:
   the `gh pr` / `gh repo view` porcelain is GraphQL-backed and a Claude Code
   session refuses GraphQL (HTTP 403), while `gh api` REST works everywhere
   (ADR-0141). Create with `ACS` as a label
   (no ticket: also `acs-exempt`), ready-for-review, never a draft; an open
   PR is updated in place (title, body, `ACS` label, base when wrong,
   ready-for-review when a draft).

   When a milestone is known (mirrors create-ticket's conditional milestone
   fill — the repo defines at least one, or the ticket/settings names one
   explicitly), both the create and the update additionally pass
   the milestone (`-F milestone=<number>`); omit the flag entirely when none is configured (this
   repo defines none today) — never an unconditional call that would error.

6. **Record.** The create/update response (or the REST "Detect" read) carries
   `number`, `html_url`, `base.ref`, `head.ref`, `draft` and labels → capture `{number, url, branch, base}` for `states.pr`.

6a. **Tracker-metadata fill (github-tracker only).** When
   `settings.tracker.provider == "github"` AND `ticket.external.key` is set
   (the same guard step 7 below uses; never without a ticket), one command
   performs every metadata write, now that the PR number is known from step 6:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" pr metadata fill \
     --pr <number> [--author <login>]
   ```

   `--author` is optional; it only tells the command whom to drop from the
   reviewer set, and omitting it makes the command resolve that login itself
   with `gh api user`. `alice`, `@alice`, `@me` and `Alice` are all the same
   login — the match strips a leading `@` and folds case on both sides,
   because CODEOWNERS writes owners `@`-prefixed while a login is passed bare.

   It assigns the PR to the authenticated user, ensures and applies the
   ticket-type label alongside the `ACS` label from step 3, requests the
   CODEOWNERS-derived reviewers (author excluded — self-review is impossible),
   adds the PR to the configured Project, and sets Status plus Priority, Story
   Points and Parent from the board's own field list. When the guard does NOT
   hold the command reports `skipped: true` and writes nothing, so the PR is
   byte-identical to an unsynced repo's output.

   **This is non-critical throughout.** Exit 0 means the pass ran, not that
   every field landed: read the printed `findings`. Each failure — a `gh` call
   that errored, a Project that defines no Status option, a field whose
   `dataType` the value cannot be written to — is one `info` finding carrying
   the exact command, ready to re-run. Carry them into the result document's
   `findings`; none of them fails the PR that steps 5–6 already completed.
   Single-select options cannot be created through the `gh` CLI, so a board
   missing an **In Review** (or **Review**) option leaves Status unchanged and
   says so rather than guessing.


7. **Tracker sync.** When `settings.tracker.provider` is `github`
   AND `ticket.external.key` is set, comment on the remote issue with the PR
   URL:
   - `github`: `gh issue comment <external.key> --body "ACS: PR #<number> opened for <ticket-id> — <url>"`
   Skip for `local` and when the run has no ticket; report an info finding when the provider
   is configured but the ticket was never synced.

   This comment plus the `Closes #<key>` body line together are what make the
   PR discoverable from the issue and vice versa — the bidirectional
   cross-reference (AC-3) holds from both directions.

Write the publish report `steps/create-pr/iter-<n>/publish.json` through `acs.py write`
(as in Finish; `references/publish.md` shows its shape: the mode, the confirmed plan's path
and the commits made, commands run with outcomes, pushed SHA, PR
number/url/base, sync result, problems hit, the pre-open self-check's
pass/fail result and, on retry, how many attempts were used, plus the
tracker-metadata-fill result — assignee/label/Project outcomes and any
findings — additive, alongside the existing fields, plus the additive
`reviewers{requested, skipped_reason, findings}` and
`project_fields{priority, story_points, parent, findings}` keys).

### GitHub call failure policy

The commands below name the operations; reach GitHub with whatever access
works in this session — normally the `gh` CLI, or the GitHub tools the session
provides when `gh` is blocked (ADR-0088 as relaxed by ADR-0141). Say which you used in the report.
Every call below is one of exactly two classes:

- **Critical** — a gate input, or a call this step cannot proceed without.
  On failure: surface the verbatim error plus ONE canonical hint from
  `acs_lib.gh_failure_hint(stderr)` (`acs_lib.GH_ACCESS_HINT` when the
  stderr names a session-access restriction, else `acs_lib.GH_GENERIC_HINT`),
  then try another access path that works here once; if there is none, STOP. Never
  report a PR, label or comment that was not actually made. Canon hint text
  (`acs_lib.GH_ACCESS_HINT`):

  > This looks like a session-level access restriction — a Claude Code
  > cloud/managed session must have the Claude GitHub App connected for this
  > organization by an org admin. A local Claude Code session uses your own
  > `gh` authentication and should not see this.

- **Non-critical** — metadata/best-effort. On non-zero exit: one `info`
  finding plus a replayable block (the exact failed command, ready to
  re-run), then continue — never abort the run for this class. Finding
  shape: `{severity, area, message, command, error, hint, replayable}`
  (`info` / `replayable: true` here).

Per-call classification in this skill:

- **Critical**: the REST open-PR detect (step 1, resume/create-vs-update);
  the REST default-branch read (step 1, base detect); the REST PR create /
  update (step 5).
- **Non-critical**: the un-draft call (step 5); the Record re-read (step 6,
  Record — a confirming re-read); the labels/assignee/milestone/type-label
  fill and its `gh label list` / `gh api …/milestones` reads (step 6a);
  Projects v2 `gh project item-add` / `field-list` / `item-edit` and the
  `gh pr diff` CODEOWNERS reviewer request (step 6a); `gh issue comment`
  (step 7, PR back-reference); the `gh run list` CI-run diagnostic read
  below.

See `references/ci-convention-check.md` for that last read's one extra rule
(an unverified check is never assumed green).

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list`
(no `--ticket` when the run has none) and reuse any recorded answer — re-asking an
answered question is a defect.
When ≥2 clarifications are open, present them to the user in ONE grouped
interaction (e.g. a single AskUserQuestion containing all open questions as a
numbered list), not serial round-trips — one interaction per question wastes
user time. Record each answer as its own `clarify.py add` entry (one `C-<n>`
per question, `--source` preserved). Never skip a question, merge two questions
into one entry, or auto-answer a question outside the existing
`--source assumption --rationale "..."` rule.
Record every Q&A — obtained interactively or relayed in a /ship brief — with
`clarify.py add --skill create-pr --question "..." --answer "..."`
BEFORE acting on it, and apply the relevant `C-n` entries yourself as you
publish (no subagent receives them). If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
The commit plan is the exception: it is never an assumption. Commits are the
user's history, so a plan is committed only on the user's own confirm — given
at the preview, or in the request itself ("commit it the way you split it",
"you decide how to split it") — recorded with `--source user`.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`).

Every run with something to commit asks ONE question — the commit preview of
step C2 — unless the request already approved the proposed plan. Ask anything
else only when reality genuinely diverges from state: the plan's branch exists
with commits the plan does not account for, or an open PR for the branch was
authored outside ACS with a conflicting base. Do not guess.

If you genuinely cannot reach the user (e.g. a non-interactive run) and the
request holds no approval of the plan: do not guess and do not commit. Write
the result document with `"status": "interrupted"` and
`"stop_reason": "needs_input"` (the question in `summary`), run the Finish
steps, and return as your final message a handoff like:

```xml
<handoff skill="create-pr" ticket-id="SHOP-123" status="needs_input">
  <summary>The working tree carries SHOP-123's changes, uncommitted; the commit plan needs the user's confirmation before anything is committed.</summary>
  <questions>
    <question>Commit plan for task/SHOP-123-bulk-import: 1. SHOP-123 Add ticket docs (docs/development/bulk-import/SHOP-123/…) 2. SHOP-123 Add tests for bulk import (tests/test_import.py) 3. SHOP-123 Implement bulk import (src/shop/importer.py). Left out: notes/todo.md. Confirm, edit, or cancel?</question>
  </questions>
  <next-step>Answer, then re-run /acs:ship SHOP-123.</next-step>
</handoff>
```

## Context pressure

If your context window is running low mid-run: do NOT burn the remainder on
work that would be lost. Flush in-flight work plus soft context (the confirmed
plan's path and the commits made so far, PR title, body status,
push/PR/sync progress, decisions, gotchas) to
`steps/create-pr/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --run <run_id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop. A plan already
confirmed is on disk; the next session resumes it rather than asking again.

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `steps/create-pr/result.json` through `acs.py write` (never the Write tool) per the
   result-document contract in INTERNALS.md:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write steps/create-pr/result.json <<'ACS_EOF'
   {
     "status": "completed",
     "summary": "3 commits on task/SHOP-123-bulk-import; PR #42 ready for review",
     "states": {
       "pr": {
         "number": 42,
         "url": "https://github.com/acme/shop/pull/42",
         "branch": "task/SHOP-123-bulk-import",
         "base": "main"
       },
       "branch": "task/SHOP-123-bulk-import",
       "commits": [
         {"id": "ticket-docs", "sha": "0f3c2ab9", "subject": "SHOP-123 Add ticket docs"},
         {"id": "slice-01-tests", "sha": "5d1e07c4", "subject": "SHOP-123 Add tests for bulk import"},
         {"id": "slice-01-code", "sha": "9a8b7c6d", "subject": "SHOP-123 Implement bulk import"}
       ]
     },
     "findings": [],
     "errors": []
   }
   ACS_EOF
   ```

   Canonical `states` key — EXACT name and shape, the /acs:merge-pr gate reads
   it: `pr` `{number, url, branch, base}` (`base` is the default branch the PR
   targets). `branch` and `commits` record what the commit phase made — the
   commits exactly as `acs.py pr commit` printed them — whenever it made any,
   also when a later step failed. On failure keep whatever is true: if the PR
   was created or updated but a later step failed, still record the real `pr`
   object; if no PR exists, omit `pr` entirely (never a stub) — the
   /acs:merge-pr gate stays closed. Put the run's findings in `findings`,
   errors in `errors`, the reason in `summary`.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-pr.py" --result-file "<the result.json you just wrote>"
   ```

   If it exits non-zero, surface its stderr verbatim — the pipeline gate stays
   closed until it succeeds. On success it finalizes the run and, when the run
   has a ticket, moves the ticket to `in_review`.

3. Report a compact summary to the user: the commits made (subject and short
   sha, in order), what was left uncommitted, PR number + URL, branch -> base,
   labels confirmed, tracker sync result (or n/a), created vs updated,
   iterations used, and the next step — review the PR yourself, then run
   `/acs:merge-pr <ticket-id>` (no ticket: `/acs:merge-pr --pr <number>`; a
   user action; the pipeline never triggers it). Under /acs:ship, instead
   return ONLY the `<handoff>` XML as your final message — status, summary
   (<=1KB) naming the commits and the PR number/URL, `<artifacts>`
   referencing `steps/create-pr/result.json`, and `<next-step>` pointing at
   /acs:merge-pr as the user's review-and-merge action.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your final message is the `<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-pr · <ticket-id | run-id> · <status>

- **Ticket**: <id> — <title> (<type>), or "none — <the run's prompt>"
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: commits made (short sha + subject, in order) and the paths left uncommitted; PR number and URL; base branch; head branch; `ACS` label applied
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files incl. `steps/create-pr/iter-<n>/commit-plan.json`, repo paths, branch, PR URL>
- **Metrics**: <wall time>
- **Next**: review the PR, then `/acs:merge-pr <ticket-id>` (no ticket: `/acs:merge-pr --pr <number>`) — a separate, reviewed step
```
