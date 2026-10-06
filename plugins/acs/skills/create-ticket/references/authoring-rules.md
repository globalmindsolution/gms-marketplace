# /acs:create-ticket — the rules every ticket author follows

Read by every type author (`create-ticket-epic-author`, `-story-author`,
`-task-author`, `-bug-author`) before it drafts, and by `create-ticket-reviewer`
before it judges. The rules every type shares live here, once; each author's own
file carries only its type's template and rules. The coordinator reads this file
too when it presents the reviewed draft (SKILL.md Step 2).

## What an author works from

Every input is a path in the author's `<task>`; it shares no memory with the
coordinator and reads each file itself:

- the run's requirements (`requirements.md`) — the request verbatim, the
  documents, an imported issue. This is the ONLY source of what is asked;
- the PRD and roadmap, and — when the request traces to a PRD feature that has
  one — the feature's living analysis (`<prd_dir>/features/<feature>/analysis/`:
  its `README.md`, then only the context files the request touches);
- the clarification ledger entries in `<context>` (`C-<n>`: the user's answers
  and recorded assumptions — binding);
- the type's description template (`<constraint name="template">`: the built-in
  `${CLAUDE_PLUGIN_ROOT}/templates/<type>-default.md`, or the repo's own
  `.acs/templates/<type>-default.md` that replaces it);
- on iteration 2, the reviewer's findings verbatim in `<context>`.

## Acceptance criteria

- Each criterion is ONE observable, checkable outcome: who or what does what,
  and what can be seen afterwards — a response code, a stored value, a message,
  a page state. Name the numbers, codes and limits the requirements give.
- Never satisfaction boilerplate: "works correctly", "is better", "no bugs",
  "handles X properly", "is fast", "is user-friendly". Rewrite it into the
  outcome it stands for, or — when the requirements do not say what it stands
  for — keep it and FLAG it (`flags`, below) for the user to revise or confirm.
  A flag is honest; a silently invented threshold is not.
- A story or task carries roughly seven criteria at most; more is a sizing
  signal (SKILL.md "The sizing rubric"), not a reason to merge two into one.
- Never invent scope: every criterion traces to a sentence of the requirements,
  a `C-<n>` answer or the feature's analysis (refined criteria there seed yours).

## PRD trace and features

- `prd_trace.feature` names the PRD feature or goal the ticket traces to (an
  epic: also its roadmap milestone), as the PRD names it; `null` when no PRD
  exists. When the request goes beyond the PRD, `prd_trace.divergence` is a
  one-line statement of how — the coordinator puts it to the user; never hide it.
- `features` are the slugs of those PRD features, each made with `python3
  "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" slug --text "<PRD feature name>"`
  (ADR-0120); `[]` when it traces to none. Never coin a slug for a feature the
  PRD does not have.

## Grounding — no invented facts

Every fact in the draft — a path, a module, a version, a persona, a number, a
reproduction step — comes from a source you read in THIS task, and `draft.md`'s
`## Sources` section cites it (file and line or heading; a command and its
output). What the inputs do not settle is an `open_questions` entry or an
`assumptions` entry with its reason — never a plausible default written as fact.

## The draft (your deliverable)

Write both files through Bash, never the Write tool (ADR-0136), each with one
`acs.py write` call to the absolute path under your task's `partition`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write <partition>/steps/create-ticket/iter-<n>/draft.json <<'ACS_EOF'
{ … }
ACS_EOF
```

`iter-<n>/draft.json` — the ticket fields the coordinator saves, plus what it
needs to ask the user:

| Key | Holds |
|---|---|
| `type` | your type: `epic`, `story`, `task` or `bug` |
| `title` | an epic's prefixed `[EPIC] `; any other type's as given |
| `description` | the template, every section filled, the HTML comments deleted, its `acs-ticket: <ticket-id>` line kept |
| `acceptance_criteria` | the criteria, as an array of strings |
| `priority` | `critical`, `high`, `medium` or `low` |
| `story_points` | an integer, or `null` |
| `features` | the slugs, or `[]` |
| `docs_only` | `true` only when the change touches documentation alone (a recommendation; the coordinator confirms it) |
| `prd_trace` | `{"feature": …, "divergence": …}` |
| `flags` | `[{"criterion": <1-based index>, "reason": "…"}]` — every criterion you could not make concrete |
| `open_questions` | what the inputs do not settle, one string each |
| `assumptions` | `[{"assumption": "…", "reason": "…"}]` |

Your type adds its own keys (your agent file names them). `draft.md` renders
the same draft for a human: the title and type, the description, the numbered
criteria with each flag beside its criterion, the trace and features, a
`## Size` paragraph (your reading against the sizing rubric, with the expected
diff surface), the open questions, and `## Sources`.

## The author report

Write `iter-<n>/<your role>.json` (e.g. `iter-1/bug-author.json`) through
`acs.py write`: `files_changed` (your two draft files), `sources` (what you
read), `commands` (each with its outcome), `findings_addressed` (iteration 2:
each reviewer finding and what you changed), `problems`.

## What an author never does

Mint a ticket, allocate an id, run `acs.py ticket save`, `new-ticket.py`,
`clarify.py add` or any tracker command, ask the user, edit a repo file, or
spawn an agent. You draft; the coordinator confirms with the user and
materializes. A genuine ambiguity is an `open_questions` entry, and a
contradiction you cannot draft around is `status="needs_input"`.
