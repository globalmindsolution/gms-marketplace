---
name: audit-security
description: Audit the repository's security and write a severity-ranked report — code weaknesses (OWASP Top 10 classes, each with its CWE), hard-coded secrets and insecure configuration, vulnerable dependencies (through the repo's own installed scanners), and, when the architecture set has one, the code against its threat model (trust boundaries in hld/data-flow.md, security conventions in hld/cross-cutting.md). Every candidate finding is handed to a fresh adjudicator that tries to refute it, so the report carries only what survived, each with file:line evidence, an exploit scenario and fix guidance. Read-only and report-only: it never edits code, docs or config, never files tickets, and never runs anything against a live system. Use when the user asks for a security audit, review, scan or assessment of the repo or a path, wants to know whether there are leaked secrets, vulnerable dependencies or injection risks, or is preparing for a pen test, a release or a compliance review. Call it as your first action on such a request — do not Glob, Grep or Read the code first, and do not look for a shell: it locates everything itself.
argument-hint: "[path | all] [code,secrets-config,dependencies,threat-model] [focus notes]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:audit-security (ADR-0123). You find security weaknesses
in the repository and report them. You never edit the code, a document, a config file
or anything else in the repo; you never file a ticket; you never run an exploit, a
network scan or any request against a deployed system. The report is your whole
output: the Development skills fix what it finds. You orchestrate two subagent roles —
the **auditor** (raises candidate findings) and the **adjudicator** (tries to refute
each one) — and never judge a finding yourself.

## Start

The scope is `$ARGUMENTS`: a path → that subtree; `all` or nothing → the repository. A
comma list naming some of `code`, `secrets-config`, `dependencies`, `threat-model`
narrows the categories (default: all four). Anything else is focus notes, passed to
every auditor as `<context>`. Then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step audit-security
```

If it exits non-zero, stop and surface its stderr verbatim. Otherwise parse the
printed context JSON: `partition`, `run_id`, `settings`, `agents` (the agent name to
spawn per role; each role's model and effort come from
`settings.models.audit-security.<role>`, inheriting when unset), `reconcile`,
`handoff_summary`, `checkout_root`. `${CLAUDE_PLUGIN_ROOT}/docs/INTERNALS.md` carries
the parts every acs skill shares.

## Resume & reconcile

If `context.reconcile` is true: re-run ONLY the auditor slices whose
`iter-1/auditor-<slice>.md` is missing and the adjudications whose
`iter-1/adjudication-<id>.json` is missing, then rebuild the report — it is always
rebuilt from those files. If `context.handoff_summary` exists, read it and continue
from where it points.

## Stage 1 — auditors

**Slices.** One auditor per category in scope, with slice ids:

| Slice | Looks for | Runs when |
|---|---|---|
| `code` · `code-<area>` | OWASP Top 10 weakness classes in source: access control, injection, crypto, authentication, integrity and deserialization, SSRF, logging of sensitive data | always; one per area on a repository whose source spans two or more disjoint top-level areas (slice id `code-<area>`, the area's directory name lowercased), else one `code` |
| `secrets-config` | credentials, keys and tokens in the tree; insecure configuration — debug on, TLS verification off, wildcard CORS, containers as root, CI that exposes secrets or runs untrusted code | always |
| `dependencies` | known-vulnerable dependencies, through the scanners the repo already has installed | a manifest or lockfile exists |
| `threat-model` | the code against the security design: each trust-boundary crossing in `hld/data-flow.md`, each security convention in `hld/cross-cutting.md` | the architecture set has either file |

A slice whose condition fails is not spawned; record it under `skipped` with the
reason (for `threat-model`: "no threat model — enable `data-flow` at /acs:setup and run
/acs:create-architecture"). Locate the architecture set the way every acs skill does:
read CLAUDE.md and the docs index it points at, then Glob for `hld/tech-stack.md`.

Each task carries `<constraint name="category">`, `<constraint name="area">` (the
paths in scope), `architecture_dir` when found, and the focus notes as `<context>`.

**One message, then wait for all.** The parallel instances are the SAME agent spawned
N times in ONE message, at most `settings.parallel.max_agents` (default 4) per
message; beyond it, waves of that size. Spawn with the Agent tool
as `context.agents.auditor` (`acs:audit-security-auditor`; fall back to the
un-namespaced name only if the runtime rejects it).

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool. If the runtime moves an agent to the
background anyway, wait for its completion notification — never poll with `sleep`
loops. The same rule governs stage 2.

Validate every auditor message — the SubagentStop hook checks each one it returns; on
an invalid message re-request it once, then fail the run with the error recorded.

## Stage 2 — adjudication

Collect the candidate findings from every auditor's `<findings>`. **De-duplicate only
exact repeats** — the same CWE at the same `file:line` — keeping the first id and
recording the others as `duplicate_of`; never merge findings that merely look alike.

**Every remaining candidate gets exactly one fresh-context adjudicator**
(`context.agents.adjudicator`, `acs:audit-security-adjudicator`), `slice` = the
finding id, at most `settings.parallel.max_agents` (default 4) per message and
waves of that size beyond it. Each receives the one finding and read
access to the repository — **neither the other findings nor which auditor raised
it**: a finding must survive on its own evidence. It is prompted to refute, and
defaults to refuted when uncertain.

| Verdict | In the report |
|---|---|
| `confirmed` | a finding at the adjudicated severity, with its `resolved_when` |
| `needs-context` | advisory — carried with what the adjudicator could not read, never dropped |
| `refuted` | counted, with its reason kept in `adjudication-<id>.json` |

An adjudicator's ruling is read from its `adjudication-<id>.json`, never from its
message: the SubagentStop hook checks the auditors' messages, not the adjudicators'
(as in /acs:review-code). An adjudication file that is missing or unreadable is
re-requested once, then the finding is carried as advisory with that reason.

**Corroboration is not a filter.** Two auditors raising one weakness does not confirm
it, and one auditor alone does not weaken it; per-finding refutation is the filter.

## The report

Write `<partition>/steps/audit-security/iter-1/report.md` yourself from the report
template — `.acs/templates/audit-security-report.md` when the repo has one, else
`${CLAUDE_PLUGIN_ROOT}/templates/audit-security-report.md` — and from the auditor
reports and the adjudication files only. Keep every `## ` section in the template's
order; each finding is one `### ` entry under its section, and an empty section says
`_None._`. The post-hook refuses a report that breaks the template and counts the
entries itself: the numbers in `states.audit` are the report's. With the built-in
template:

1. **Scope and coverage** — the paths audited, the slices run and skipped (with
   reasons), the scanners each dependency auditor ran and the ones the repo does not
   have. A category with no scanner and no manual coverage is said to be uncovered,
   never reported as clean.
2. **Summary**, then one section per severity, `Critical` → `High` → `Medium` →
   `Low`: the confirmed findings at their adjudicated severity, by file. Each: id,
   title, CWE (and OWASP category), `file:line`, evidence, exploit scenario, fix
   guidance, `resolved_when`.
3. **Advisory** — the `needs-context` findings.
4. **Refuted** — each with its one-line reason; the full ruling stays in
   `adjudication-<id>.json`.

**A secret's value never appears** in the report, the result or your messages:
name its location, its kind and a redacted form (the first 4 characters and the
length). A secret in the tree is reported as live until someone says it has been
rotated.

## User interaction

None. The audit asks nothing and offers nothing: no ticket, no fix, and it never
opens a grouped interaction. If the scope argument names a path that does not exist,
stop with that as the summary.

**Clarification ledger first.** Before settling anything an answer would decide — a
focus note that names no path, a scope that matches two areas — run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list` and reuse any
recorded answer. With none, take the wider reading, record it with
`clarify.py add --skill audit-security --question "..." --source assumption
--rationale "..."` (one `C-<n>` per decision; never skip, merge or auto-answer a
question outside that assumption rule), and say so under **Scope and coverage**.

## Context pressure

If context runs low: write the in-flight state to
`steps/audit-security/handoff-context.md`, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --summary "<done / in-flight / next>"`,
and give the user the `continue_with` command it prints.

## Finish

MANDATORY, also on failure. Write `steps/audit-security/result.json` per the
result-document contract in INTERNALS.md, with `states` (the post-hook re-counts the
severities, `advisory` and `refuted` from the report):

```json
{
  "status": "completed",
  "summary": "audited the repository: 1 high, 2 medium confirmed; 1 advisory; 5 refuted",
  "states": {
    "audit": {
      "scope": "all",
      "report": "steps/audit-security/iter-1/report.md",
      "critical": 0, "high": 1, "medium": 2, "low": 0,
      "advisory": 1, "refuted": 5,
      "scanners": ["pip-audit"],
      "skipped": ["threat-model"]
    }
  },
  "findings": [],
  "errors": []
}
```

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-audit-security.py" --result-file "<the result.json you just wrote>"
```

## Completion report (normative)

Every terminal outcome ends your final message with the standard block (INTERNALS.md
"Completion report"), rendered only AFTER the post-hook succeeded:

```markdown
## /acs:audit-security · <scope> · <status>

- **Ticket**: none — a read-only, report-only audit
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: confirmed findings by severity (critical / high / medium / low), advisory, refuted; slices run and skipped; scanners run
- **Findings**: <every critical and high finding, one line each with its file:line, or "none confirmed">
- **Artifacts**: the report path in the workspace
- **Metrics**: auditors <n> · adjudicators <n> · <wall time>
- **Next**: `/acs:create-ticket` for a finding to fix; `/acs:setup` to enable `data-flow` when the threat model was skipped
```
