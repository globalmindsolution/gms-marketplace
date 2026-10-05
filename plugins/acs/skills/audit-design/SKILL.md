---
name: audit-design
description: Audit the system design against the code — compare the architecture set (the HLD and every lld/<feature>/ document, or one feature's) with the implementation and report every gap, classified as unimplemented (designed, not built), undocumented (built, not designed) or drifted (both, disagreeing), each cited on both sides, with each document's design status and version. Read-only: it never edits a document or the code. Use when onboarding acs onto an existing repo, before a design review, after a run of tickets, or whenever the user asks whether the docs still match the code, what is designed but not built, or where the architecture has drifted. Call it as your first action on such a request — do not Glob, Grep or Read for the docs, ticket or repo files, and do not look for a shell: it locates all of them itself.
argument-hint: "[feature-slug | hld | all] [focus notes]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:audit-design (ADR-0122). You find where the system
design and the code disagree, and you report it. You never edit a design document, the
code, or anything else in the repo: the Design skills fix the design and the
Development skills the code; your report is what they start from. You orchestrate one
subagent role, the **gap analyst**, and never compare the docs to the code yourself.

## Start

Locate the architecture set the way every acs skill does — documents are found, not
configured: read CLAUDE.md and the docs index it points at, then Glob for
`hld/tech-stack.md`. Found → its directory is `<architecture_dir>`. None → say "no
architecture set found — /acs:create-architecture can baseline one" and stop: there is
nothing to audit.

The scope is `$ARGUMENTS`: a feature slug → `hld/` plus `lld/<slug>/`; `hld` → the HLD
only; `all` or nothing → the HLD and every `lld/<feature>/`. Then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step audit-design --args "$ARGUMENTS"
```

An audit needs no ticket: `step start` opens a run over the invocation (or resumes
this checkout's interrupted audit), and the post-hook concludes it. If it exits non-zero, stop and surface its stderr verbatim. Otherwise parse the
printed context JSON: `partition`, `run_id`, `settings`, `agents` (the agent name to
spawn per role; the gap analyst's model and effort come from
`settings.models.audit-design.gap-analyst`, inheriting when unset), `reconcile`,
`handoff_summary`, `checkout_root`. `${CLAUDE_PLUGIN_ROOT}/docs/INTERNALS.md` carries
the parts every acs skill shares.

## Resume & reconcile

If `context.reconcile` is true: re-run ONLY the gap-analyst slices whose own report
`iter-1/gaps-<id>.md` is missing, in one message, then redo the join with
`acs.py notes merge`; the joined file is always rebuilt from the slice files. If
`context.handoff_summary` exists, read it and continue from where it points.

## The audit

Read each in-scope document's version front matter — in the SAME message as the
gap-analyst spawn below, since the analysts compare every document whatever its front
matter says and nothing they do waits on it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design check <every in-scope document>
```

A document with no or invalid front matter is itself a finding (`unversioned`) in the
report — the audit still compares it. You need each document's status only when you
read the joined report (below), after the analysts return.

**Slice by code area.** On a repository whose source spans two or more disjoint
top-level areas (packages, services or apps), spawn one gap analyst per area — slice id
the area's directory name, lowercased — else one with `slice="repo"`. Each task carries
`<constraint name="area">`, `<constraint name="scope">` (the in-scope document paths)
and `architecture_dir`; its `<inputs>` are the in-scope documents.

**One message, then wait for all.** The parallel instances are the SAME agent spawned N
times in ONE message, at most `settings.parallel.max_agents` (default 4) per message;
beyond it, waves of that size. Spawn with the Agent tool as
`context.agents.gap-analyst` (`acs:audit-design-gap-analyst`; fall back to the
un-namespaced name only if the runtime rejects it).

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool. If the runtime moves an agent to the
background anyway, wait for its completion notification — never poll with `sleep`
loops.

**Join deterministically** — never merge prose by hand:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/audit-design/iter-1/gaps.md \
  <partition>/steps/audit-design/iter-1/gaps-<id>.md …
```

Validate every message — the SubagentStop hook checks each one a subagent returns; on
an invalid message re-request it once, then fail the run with the error recorded.

**Read the report against each document's status.** An **unimplemented** element in a
`proposed` or `approved` document is the design ahead of the code — expected, listed as
*planned*, not a defect. In an `implemented` document it is a regression: the code no
longer does what the design says it does. **Undocumented** and **drifted** are gaps
whatever the status.

## The report

Write `<partition>/steps/audit-design/iter-1/report.md` through `acs.py write` (as in Finish) from the
report template —
`.acs/templates/audit-design-report.md` when the repo has one, else
`${CLAUDE_PLUGIN_ROOT}/templates/audit-design-report.md` — from the joined `gaps.md`
and the `design check` output only. Keep every `## ` section in the template's order;
each gap is one `### ` entry under its section, and an empty section says `_None._`.
An unimplemented gap goes under **Unimplemented** only in an `implemented` document;
in a `proposed` or `approved` one it goes under **Planned**. The post-hook refuses a
report that breaks the template and counts the entries itself: the numbers in
`states.audit` are the report's, whatever the result document says.

## User interaction

**Clarification ledger first.** Before asking anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list` and reuse any recorded
answer. The audit itself asks nothing. At the end, offer ONE grouped interaction: which gap
groups to ticket. On a yes, run `/acs:create-ticket` (Skill tool) once per chosen group
with the group's gaps and citations as its prompt, and list the ticket ids. Record the
answer with `clarify.py add --skill audit-design --question "..." --answer "..."` before
acting on it. If you cannot reach the user, ticket nothing and say so.

## Context pressure

If context runs low: write the in-flight state to
`steps/audit-design/handoff-context.md`, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --summary "<done / in-flight / next>"`,
and give the user the `continue_with` command it prints.

## Finish

MANDATORY, also on failure. Write `steps/audit-design/result.json` through `acs.py write`
(never the Write tool) per the result-document contract in INTERNALS.md, with `states`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write steps/audit-design/result.json <<'ACS_EOF'
{
  "status": "completed",
  "summary": "audited hld + 3 features against the code: 4 gaps, 2 planned",
  "states": {
    "audit": {
      "scope": "all",
      "report": "steps/audit-design/iter-1/report.md",
      "unimplemented": 1, "planned": 2, "undocumented": 2, "drifted": 1, "unversioned": 0,
      "tickets": ["SHOP-31"]
    }
  },
  "findings": [],
  "errors": []
}
ACS_EOF
```

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-audit-design.py" --result-file "<the result.json you just wrote>"
```

## Completion report (normative)

Every terminal outcome ends your final message with the standard block (INTERNALS.md
"Completion report"), rendered only AFTER the post-hook succeeded:

```markdown
## /acs:audit-design · <scope> · <status>

- **Ticket**: none — a read-only audit (tickets it minted are under Results)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: gaps by kind (unimplemented / planned / undocumented / drifted / unversioned), each with its document and code citation; tickets created
- **Findings**: <regressions in implemented documents, unversioned documents, or "none">
- **Artifacts**: the report path in the workspace
- **Metrics**: gap-analyst slices <n> · <wall time>
- **Next**: `/acs:create-architecture` or the LLD skill for a design gap; `/acs:ship <ticket>` for a code gap
```
