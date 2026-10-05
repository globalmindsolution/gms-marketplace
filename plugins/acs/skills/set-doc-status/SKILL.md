---
name: set-doc-status
description: Approve, deprecate, mark implemented or reopen the product's versioned documents — the PRD, the roadmap, each feature's analysis, the HLD and each feature's LLD — by picking whole features, design areas or single documents from one grouped list that shows every document's status and version, then moving all of them at once along the legal status transitions, with who moved them and why recorded in their front matter. Use whenever the user says a feature's documents, the PRD or the design were approved or signed off, wants a design or PRD document deprecated or retired, marked implemented once built, or reopened as proposed, or wants to choose which features to approve. Call it as your first action on such a request — do not Glob, Grep or Read for the documents, ticket or repo files, and do not look for a shell: it lists every versioned document itself.
argument-hint: "[status] [feature|doc…] [--reason TEXT]"
disallowed-tools: Edit, NotebookEdit, Write
---

You are the coordinator of `/acs:set-doc-status`, the document-status utility
skill (ADR-0130). This is NOT a hooked pipeline skill: no `acs step start`, no
pre/post hooks, no subagents, no reflection loop, no run. You do the work
inline with Bash and AskUserQuestion.

Every versioned document opens with a front-matter block (ADR-0122):

```yaml
---
status: approved            # proposed | approved | implemented | deprecated
version: 3                  # bumped on every change to the document
tickets: ["SHOP-12"]
feature: wishlist           # LLD documents and feature analyses only
status_by: Ana Lima <ana@example.com>
status_at: 2026-10-05T09:12:44Z
status_reason: signed off at the product council
---
```

A status moves ONLY through `acs.py design status`, along a legal transition —
never by editing the block (you cannot: Edit and Write are disallowed here).
The legal moves are `proposed → approved | deprecated`, `approved → proposed |
implemented | deprecated`, `implemented → proposed | deprecated`; `deprecated`
is final. A status move never changes `version` — only a change to the
document's content bumps it (`design bump`, run by the skills that write it).

You write nothing yourself, and you never branch, stage, commit or push
(ADR-0127): the CLI rewrites the front matter in the working tree and the
changes stay there for `/acs:create-pr`.

## Step 1 — List the documents

MANDATORY first action:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design list
```

Narrow it when the arguments already name a phase or a feature:
`--phase discovery|design`, `--feature <slug>`. It prints
`{ok, groups: [{phase, key, label, feature?, docs: [{path, status, version,
problems, allowed}]}]}`, deterministically ordered:

- **Discovery** — the PRD (`<prd_dir>/prd.md`), the roadmap, and each feature's
  living analysis (`<prd_dir>/features/<f>/analysis.md`);
- **Design** — the HLD (`<architecture_dir>/hld/*.md`) and each feature's LLD
  (`<architecture_dir>/lld/<f>/{api,data,flows,components}/**`). The per-run
  design records under `lld/<f>/<id>/` are not versioned documents and are
  never listed.

Group labels read `PRD` (the PRD and the roadmap together), `feature <f>
analysis`, `HLD` and `LLD <f>`; a feature's groups carry `feature`. Paths are
repo-relative: run every command from the checkout root. `allowed` lists the
legal moves OTHER than the document's current status; `problems` is non-empty
when its front matter is missing or invalid (and `allowed` is then empty).

If the command exits non-zero, STOP and surface its stderr verbatim. If
`groups` is empty, there is nothing to move: report status `completed` with
"no versioned documents found" and point at the skills that create them
(`/acs:create-prd`, `/acs:analyze-requirements`, `/acs:create-architecture`,
`/acs:create-data-design`, `/acs:create-flows`).

A document with `problems` cannot be moved: never offer it, and list it under
Findings with its problems (the skill that writes it gives it front matter,
or `acs.py design init` does). A document whose `allowed` is empty (a
`deprecated` one) is final: never offer it either. A group left with no
offerable document is not offered.

## Step 2 — Read the arguments

`$ARGUMENTS` may carry, in any order:

- a **status** — `approved`, `implemented`, `deprecated` or `proposed`; accept
  the verbs too (`approve`, `deprecate`, `retire` → `deprecated`, `reopen` →
  `proposed`, `implement`/`built` → `implemented`);
- **targets** — a feature slug (every group whose `feature` is that slug, in
  BOTH phases: its analysis and its LLD — `design list --feature <slug>`), a
  group key or label (`prd` or `PRD` for the PRD with its roadmap, `hld`), a
  document path as `design list` prints it, or a plain name of one document
  (`roadmap` → the roadmap's path);
- `--reason TEXT` — why, recorded as `status_reason`;
- `--by NAME` — who decided, recorded as `status_by`. Omit it and the CLI
  records the git identity (`git config user.name <user.email>`).

A target that matches no listed group or document is not guessed at: tell the
user which one and show the list (Step 3), or stop when you cannot ask. When
the arguments name the status AND the targets (and, for `deprecated`, the
reason), skip Steps 3 and 4 entirely and go to Step 5: the command line is the
user's choice. When they name only some of it, ask only for what is missing.

## Step 3 — Pick the documents (ONE grouped ask)

Ask ONE AskUserQuestion, `multiSelect: true` on every question, one question
per phase that has an offerable document (`Discovery`, then `Design`):

- **One option per group** — a feature's analysis, a feature's LLD (a whole
  design area), the HLD, the PRD with its roadmap. Its `label` is the group's
  label (`LLD wishlist`, `HLD`, `PRD`); its
  `description` lists every document in it as `<file name> · <status> v<version>`,
  e.g. `features/wishlist/analysis.md · proposed v2` or
  `api/wishlist-api.md · proposed v1; flows/add-item.md · proposed v1`. Always
  show the status and the version — the user is approving a specific version.
- **A single document** — a group of one is that document's option. To pick
  one document out of a larger group, the user types its path in the
  question's free-text answer; say so in the question text.
- **Paging** — a question takes at most 4 options. When a phase has more than
  4 groups, split it into pages — `Design (1/2)`, `Design (2/2)` — each its own
  question in the SAME AskUserQuestion; at most 4 questions per call, and only
  beyond that a second call with the remaining pages. Order groups with a
  `proposed` document first (they are the ones waiting for a decision), then
  the order `design list` printed.

The selection is the union of every picked group's documents and every typed
path. Nothing picked → status `completed`, "nothing selected", and stop.

## Step 4 — Pick the target status, then confirm

**Target.** Offer a status only when EVERY selected document either has it in
`allowed` or already is at it, and at least one is not at it yet — approving
a feature whose analysis is already approved and whose LLD is proposed is one
move. Order: `approved` first when any selected document is
`proposed`, then `implemented`, `proposed`, `deprecated`. Ask it as ONE
AskUserQuestion with two questions: the target status, and an optional reason
(options `No reason`, plus free text). When the intersection is empty, the
selection mixes documents no single move fits (a `deprecated` one, or an
`implemented` one with a `proposed` one asked to become `implemented`): say
which documents block which moves and go back to Step 3 once.

**Reason.** A move to `deprecated` needs one — ask for it again when the
answer was `No reason`; still none → stop with status `failed`, "deprecation
needs a reason", and change nothing. For any other move it is optional.

**Exclusions.** A selected document already at the target status is dropped
from the move and reported as "already <status>", never re-recorded.

**Confirm.** Show the exact plan, one line per document —
`<path>: <status> v<version> → <target>` — plus the reason and who will be
recorded, and ask one yes/no AskUserQuestion (`Apply`, `Cancel`). `Cancel` →
status `completed`, "nothing changed", and stop.

**Headless.** When AskUserQuestion is unavailable (a non-interactive session)
and the arguments did not decide everything, change nothing: print the list
and the exact `design status` command that would apply the user's request, and
finish with status `interrupted`, `stop_reason: needs_input`.

## Step 5 — Apply (atomic)

ONE command over every document in the plan:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design status --set <target> \
  [--by "<name>"] [--reason "<reason>"] <doc> <doc> …
```

It validates every document first — it exists, its front matter is valid, the
move is legal — and writes none of them when any one is refused, so a refusal
leaves the tree exactly as it was. On a non-zero exit, surface its stderr
verbatim and finish with status `failed`; never retry the documents one by one
to get around the refusal, and never edit a front-matter block by hand.

Then show what changed, from the tree itself:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design check <doc> <doc> …
git status --porcelain -- <doc> <doc> …
```

`design check` must report each document at the target status with its
version unchanged and no problems; a mismatch is a Finding.

## Step 6 — Deliver: local changes only

Nothing is committed (ADR-0127). The changed documents stay as uncommitted
changes on whatever branch is checked out. List every path `git status`
reported, and point the user at `/acs:create-pr` with a prompt that says what
the change is, e.g. `/acs:create-pr "Approve the wishlist design"` — it commits
them on a branch of their own and opens the PR the team reviews. The PR's
review is where the team sees the recorded decision.

## Completion report (normative)

Every terminal outcome ends your final message with the standard block
(INTERNALS.md "Completion report"); the Ticket line reads **Scope**, since no
ticket or run is involved, and Metrics carries no iterations (no loop runs):

```markdown
## /acs:set-doc-status · <target status> · <status>

- **Scope**: <n> document(s) across <the picked features / design areas / single documents>
- **Status**: <completed|failed|interrupted> — <one line; `stop_reason` when interrupted>
- **Results**: <one line per document: `<path>`: <from> v<version> → <target>; "already <status>" lines; or "nothing changed">
- **Findings**: <refusals verbatim, documents not offered because of `problems`, or "none">
- **Artifacts**: <the uncommitted repo paths `git status` listed, or "none">
- **Metrics**: <n> moved · <wall time>
- **Next**: review the listed files, then `/acs:create-pr "<what the status change is>"` to commit them and open the PR
```
