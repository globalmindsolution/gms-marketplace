"""acs_lib.phases — where the plugin's files live, and which skills exist.

Two things `acs_lib.workflow` needs before it can read a workflow at all, and
that several callers need WITHOUT one: the plugin-relative paths
(`workflows/`, `skills/`, `schemas/`) and the skill registry itself,
`workflows/phases.yaml` — the single source for which skills ship, which phase
each belongs to, which are aliases of another, which are internal legs of an
entry point, and which subagent roles each owns.

Keeping this here rather than in `workflow.py` is what lets a caller ask "is
`code-small` a leg of `code`?" without loading, resolving and validating a
pipeline document to find out.

`ship.yaml` alone may be overridden by the consumer repo; `phases.yaml` is the
plugin's own registry and has no override, which is why `phases_path` takes a
plugin root and `resolve_workflow` takes a checkout root.
"""

import os

from ._common import WorkflowError, plugin_root, read_json
from . import schemasubset
from . import yamlsubset
from .yamlsubset import YamlSubsetError

WORKFLOWS_DIRNAME = "workflows"
SKILLS_DIRNAME = "skills"
PHASES_FILENAME = "phases.yaml"
SHIP_FILENAME = "ship.yaml"
#: A consumer override replaces the plugin's ship.yaml wholesale.
OVERRIDE_WORKFLOW_RELPATH = os.path.join(".acs", "workflows", "ship.yaml")
SHIP_SCHEMA_FILENAME = "ship-workflow.schema.json"
PHASES_SCHEMA_FILENAME = "phases.schema.json"

#: The five groups phases.yaml may declare, in pipeline order.
PHASE_GROUPS = ("design", "build", "test", "ship", "utility")
#: The groups ship.yaml may name a step from.
SHIP_PHASES = ("build", "test", "ship")
#: Ship skills a human always drives, never a workflow step.
SHIP_EXCLUDED_SKILLS = ("merge-pr", "release")


#: The registry's own failures ARE workflow failures: `phases.yaml` and
#: `ship.yaml` are two documents of one contract, and a caller that catches one
#: should not have to know which of them it read.
PhasesError = WorkflowError


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def workflows_dir(root=None):
    return os.path.join(root or plugin_root(), WORKFLOWS_DIRNAME)


def phases_path(root=None):
    return os.path.join(workflows_dir(root), PHASES_FILENAME)


def skills_dir(root=None):
    """The plugin's skills/ tree -- where an `internal` leg must have its
    directory. Always the plugin's own, never a consumer override: phases.yaml
    has no override (only ship.yaml does), like _load_schema below."""
    return os.path.join(root or plugin_root(), SKILLS_DIRNAME)


def default_workflow_path(root=None):
    return os.path.join(workflows_dir(root), SHIP_FILENAME)


def override_workflow_path(checkout_root):
    return os.path.join(checkout_root, OVERRIDE_WORKFLOW_RELPATH)


def schema_path(name, root=None):
    return os.path.join(root or plugin_root(), "schemas", name)


def load_schema(name):
    schema = read_json(schema_path(name))
    if not isinstance(schema, dict):
        raise PhasesError("cannot read the schema at %s" % schema_path(name))
    return schema


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

def load_phases(path=None):
    """workflows/phases.yaml, schema-checked, with every skill listed exactly
    once across the five groups, the `aliases` keys and the `internal` keys,
    every alias pointing at a registered skill, and every internal leg owning a
    skills/<dir> and pointing at a phase-listed skill that is not itself a leg.
    `aliases` and `internal` are always present (an empty mapping when the file
    has none)."""
    path = path or phases_path()
    try:
        doc, lines = yamlsubset.parse_file(path)
    except YamlSubsetError as exc:
        raise PhasesError(exc.reason, path=exc.path, line=exc.line)
    errors = schemasubset.schema_errors(load_schema(PHASES_SCHEMA_FILENAME), doc)
    if errors:
        node, message = errors[0]
        raise PhasesError("%s: %s" % (schemasubset.pointer(node), message), path=path,
                            line=yamlsubset.line_for(lines, node))
    seen = {}
    for group in PHASE_GROUPS:
        for skill in doc["phases"][group]:
            if skill in seen:
                raise PhasesError("skill %r is listed under both %s and %s" % (skill, seen[skill], group),
                                    path=path, line=yamlsubset.line_for(lines, ("phases", group)))
            seen[skill] = group
    aliases = doc.get("aliases") or {}
    for alias, target in aliases.items():
        if alias in seen:
            raise PhasesError("alias %r is also a registered skill" % alias, path=path,
                                line=yamlsubset.line_for(lines, ("aliases", alias)))
        if target not in seen:
            raise PhasesError("alias %r points at unregistered skill %r" % (alias, target), path=path,
                                line=yamlsubset.line_for(lines, ("aliases", alias)))
    doc["aliases"] = aliases
    internal = doc.get("internal") or {}
    for leg, entry in internal.items():
        line = yamlsubset.line_for(lines, ("internal", leg))
        if leg in seen:
            raise PhasesError("internal leg %r is also a registered skill" % leg, path=path, line=line)
        if leg in aliases:
            raise PhasesError("internal leg %r is also an alias" % leg, path=path, line=line)
        if entry in internal:
            raise PhasesError("internal leg %r points at %r, which is itself an internal leg" % (leg, entry),
                                path=path, line=line)
        if entry not in seen:
            raise PhasesError("internal leg %r points at unregistered entry point %r" % (leg, entry),
                                path=path, line=line)
    for leg in internal:
        if not os.path.isdir(os.path.join(skills_dir(), leg)):
            raise PhasesError("internal leg %r has no skills/%s directory" % (leg, leg), path=path,
                                line=yamlsubset.line_for(lines, ("internal", leg)))
    doc["internal"] = internal
    return doc


def registered_skills(phases=None):
    """Every registered skill, in group then file order (aliases excluded)."""
    phases = phases or load_phases()
    return [skill for group in PHASE_GROUPS for skill in phases["phases"][group]]


def skill_aliases(phases=None):
    """{alias: target} -- a skill directory that forwards to a registered skill."""
    return dict((phases or load_phases())["aliases"])


def skill_legs(phases=None):
    """{internal-leg: entry-point} -- a skill that keeps its SKILL.md, agents,
    hooks and gate and stays Skill-invocable, but whose only user-facing
    command is the entry point it serves. `{}` when the registry declares none."""
    return dict((phases or load_phases())["internal"])


def skill_agents(phases=None):
    """{skill: [role, ...]} -- the subagent roles each skill owns (ADR-0092).

    A skill declares the machinery its work needs; nothing is inferred from
    whether it is hooked. A skill absent from the map owns no subagents, which
    is the right answer for a mechanical action or a dispatcher. `{}` when the
    registry declares none.
    """
    return dict((phases or load_phases()).get("agents") or {})


def agent_roles_of(skill, phases=None):
    """The roles `skill` owns, `[]` when it owns none."""
    return list(skill_agents(phases).get(skill, []))


def entry_point_of(skill, phases=None):
    """The entry point an internal leg serves, else None (a user-facing skill
    is nobody's leg)."""
    return (phases or load_phases())["internal"].get(skill)


def phase_of(skill, phases=None):
    """The group a skill belongs to, else None. An alias resolves to its
    target and an internal leg to its entry point, so an internal leg reports
    the group of the command a user actually runs."""
    phases = phases or load_phases()
    skill = phases["aliases"].get(skill, skill)
    skill = phases["internal"].get(skill, skill)
    for group in PHASE_GROUPS:
        if skill in phases["phases"][group]:
            return group
    return None


def allowed_ship_skills(phases=None):
    """The user-facing skills a ship.yaml step may name: build + test + ship,
    minus SHIP_EXCLUDED_SKILLS. No internal leg is here — a leg is not a
    command, and this list has always meant "commands the pipeline may run"."""
    phases = phases or load_phases()
    return [skill for group in SHIP_PHASES for skill in phases["phases"][group]
            if skill not in SHIP_EXCLUDED_SKILLS]


def allowed_step_skills(phases=None):
    """What a step's `skill` may resolve to: allowed_ship_skills(), plus the
    internal legs those skills serve as entry point. The schema's `skillName`
    enum mirrors this list.

    The legs are admissible only HERE, and only through a per-path mapping: the
    `code` step names `code-standard` on one path and `code-trivial` on another
    (ADR-0095). Keeping that separate from allowed_ship_skills() preserves what
    that function has always meant — a leg still is not a command — and makes
    the one place legs become nameable explicit. A leg is admissible exactly
    when the command it serves is, so a leg of `merge-pr` could never slip in."""
    phases = phases or load_phases()
    entry_points = allowed_ship_skills(phases)
    legs = [leg for leg, entry in phases["internal"].items() if entry in entry_points]
    return entry_points + sorted(legs)
