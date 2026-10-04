# 0115 — Models are set per skill and role, and applied through generated agents

**Status**: Accepted · **Date**: 2026-10-02

**Supersedes**: the model-tier mechanism wherever earlier ADRs describe it —
the `planner` / `executor` / `verifier` tiers, `models.overrides.<skill>.<tier>`
and `context.models` (notably [0092](0092-skill-machinery-declared-per-skill.md)
and [0109](0109-subagents-per-skill-logic-and-no-skill-manifest.md)). Their other
decisions stand.

## Context

`settings.models` held three keys, one per tier, plus per-skill overrides. A
role's kind picked its tier, so a repo could not give the `review-code`
adjudicator more effort than the `lens` without moving every judge, and the
tiers' only effect was a coordinator reading `context.models` and passing the
values when it spawned the agent.

That last part no longer works for effort. The Agent tool takes a per-call
`model` but no per-call effort; an agent's effort is set by its frontmatter.

We checked what a project can do about a plugin's agents (Claude Code 2.1.286):

- A project agent with the plugin agent's own name (`acs:code-implementer`) does
  not replace it. The plugin's prompt runs.
- A project agent cannot use the `acs:` namespace at all.
- A project agent with a plain name (`acs-code-implementer`) registers, can be
  spawned by name, and its frontmatter `model:` and `effort:` are honoured.
  `SubagentStart` fires for it, so a hook can match it.
- Effort is not honoured on every model: a `low` on haiku was recorded as none.

## Decision

1. **`settings.models.<skill>.<role>` = `{model, effort}`**, both optional. The
   skills and roles are the agents the plugin ships, read from `agents/`; an
   unknown one is a settings error that lists the valid ones. There is no
   default key: an absent skill, role or field, or the value `inherit`, inherits
   the parent session's own value.
2. **A model is an alias, a full model id or `inherit`.** The scaffold pins full
   ids so an eval baseline is not moved by an alias that advances on its own.
3. **The settings file is scaffolded in full.** `acs.py settings scaffold
   --write` adds every skill and role with the recommended values and never
   changes an entry that is there. The recommendation lives in one table in
   `acs_lib.models`; nothing at run time reads it. A new agent has no entry, so
   it inherits, until the scaffold runs again.
4. **Applied through generated agents.** For each entry that sets a value,
   `acs step start` (or `acs.py agents sync`) writes
   `.claude/agents/acs-<skill>-<role>.md`: the plugin agent's own file, renamed,
   with `model:` and `effort:` set and a marker carrying a digest of its source.
   It is rewritten when the plugin's prompt or the settings change, removed when
   its entry stops setting anything, and a file without the marker is never
   touched. The files are derived and gitignored.
5. **Coordinators spawn the name in `context.agents.<role>`** — `acs:<agent>`
   where nothing is set, `acs-<agent>` where it is — and pass no model of their
   own. The analyze-requirements controller prints the same names in its actions.
6. **The lifecycle hooks match `^acs[:-]`** and read the skill and role from
   either spelling, so artifact validation and the file-map guard cover a
   generated copy exactly as they cover the plugin's.

## Consequences

- Model and effort are configurable per agent per skill, in one place.
- Settings that set effort on a model that ignores it have no effect there; the
  scaffold sets none on haiku.
- Each generated copy is a full copy of its plugin agent. The digest keeps it
  from going stale across a plugin update, but only a step start (or an explicit
  sync) refreshes it.
- `code-implementer` serves all four `/acs:code` delivery legs, so one
  `code.implementer` entry covers them.
- The settings file grows by about sixty generated lines. Nobody edits them
  unless they want a change.
