"""acs_lib.models — `settings.models`: the model and effort of each subagent.

Shape: `models.<skill>.<role> = {"model": ..., "effort": ...}`, both fields
optional. An absent skill, role or field -- or the value `inherit` -- inherits
the parent session's own value; nothing here has a default of its own.

The skills and roles a settings file may name are the agents the plugin ships
(`agents/<skill>-<role>.md`), read from that directory, so a new agent never
needs a list edited here.

`recommended()` is the scaffold's table and nothing else: `scaffold()` writes it
into a settings file, and no gate or spawn reads it. What runs is what the
settings file says.
"""

import os

from ._common import GateError
from .skills import ROLE_KINDS, agents_dir, split_agent_name

#: Reasoning-effort values a subagent may carry. `inherit` is "leave it".
EFFORTS = ("low", "medium", "high", "xhigh", "max", "inherit")

#: The value that means "do not override".
INHERIT = "inherit"

#: Pinned in the scaffold so an eval baseline is not moved by a model alias
#: that advances on its own. A new model generation is a change to these two.
OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5-5"

#: role -> (model, effort), the scaffold's starting values. Decisions upstream
#: of the code (scope, plan, design) and the fresh judges get depth; producing a
#: document against a spec and the mechanical checks stay cheap.
_RECOMMENDED = {
    # survey / plan / design: scope and design decisions compound downstream
    "surveyor": (OPUS, "high"),
    "planner": (OPUS, "high"), "architect": (OPUS, "high"),
    "designer": (OPUS, "high"),
    "impact-analyst": (SONNET, "high"), "analyst": (SONNET, "high"),
    "gap-analyst": (SONNET, "high"), "auditor": (OPUS, "high"),
    # write: produced against an upstream spec, then reviewed
    "author": (SONNET, "medium"), "contract-author": (SONNET, "medium"),
    "test-designer": (SONNET, "medium"), "doc-updater": (SONNET, "medium"),
    "test-writer": (SONNET, "medium"),
    # create-ticket's typed draft authors (ADR-0138), reviewed before the user sees them
    "epic-author": (SONNET, "medium"), "story-author": (SONNET, "medium"),
    "task-author": (SONNET, "medium"), "bug-author": (SONNET, "medium"),
    "implementer": (SONNET, "medium"),
    # judge: re-derives fresh, and is the gate before approval
    "reviewer": (OPUS, "high"), "plan-reviewer": (OPUS, "high"),
    "contract-reviewer": (OPUS, "high"),
    "drift-reviewer": (OPUS, "high"), "impact-reviewer": (OPUS, "high"),
    "adjudicator": (OPUS, "xhigh"),
    "lens": (SONNET, "high"), "trace-reviewer": (SONNET, "high"),
    # mechanical: run a command or compare against a frozen list
    "suite-runner": (SONNET, "medium"),
}


def recommended(role):
    """{"model", "effort"} the scaffold writes for `role`."""
    model, effort = _RECOMMENDED[role]
    return {"model": model, "effort": effort}


def agent_names(root=None):
    """Every shipped agent's name (`<skill>-<role>`), sorted."""
    base = agents_dir(root)
    if not os.path.isdir(base):
        return []
    return sorted(f[:-len(".md")] for f in os.listdir(base) if f.endswith(".md"))


def inventory(root=None):
    """{skill: [role, ...]} for every shipped agent, both sorted. An agent
    whose name does not split into a shipped skill and a known role is left
    out; `test_every_agent_splits` fails on one."""
    out = {}
    for name in agent_names(root):
        skill, role = split_agent_name(name)
        if skill:
            out.setdefault(skill, []).append(role)
    return {skill: sorted(roles) for skill, roles in sorted(out.items())}


def scaffold(root=None):
    """The full `models` block: every skill, every role, the recommended values."""
    return {skill: {role: recommended(role) for role in roles}
            for skill, roles in inventory(root).items()}


def merge_missing(models, root=None):
    """`models` plus every scaffold entry it lacks; nothing it has is changed.
    Returns (merged, added) where `added` lists `skill.role` strings."""
    merged = {skill: dict(roles) for skill, roles in (models or {}).items()
              if isinstance(roles, dict)}
    added = []
    for skill, roles in scaffold(root).items():
        for role, value in roles.items():
            if role not in merged.get(skill, {}):
                merged.setdefault(skill, {})[role] = value
                added.append("%s.%s" % (skill, role))
    return merged, added


def validate_models(models, root=None):
    """Raise GateError on a `models` block that names an unknown skill or role,
    or carries a malformed field. Absence is never an error."""
    if models is None:
        return
    if not isinstance(models, dict):
        raise GateError("models must be an object of skill -> role -> {model, effort}.")
    known = inventory(root)
    for skill, roles in models.items():
        if skill not in known:
            raise GateError("models.%s: unknown skill (allowed: %s)."
                            % (skill, ", ".join(sorted(known))))
        if not isinstance(roles, dict):
            raise GateError("models.%s must be an object of role -> {model, effort}." % skill)
        for role, value in roles.items():
            if role not in known[skill]:
                raise GateError("models.%s.%s: unknown role (allowed: %s)."
                                % (skill, role, ", ".join(known[skill])))
            _check_agent("models.%s.%s" % (skill, role), value)


def _check_agent(path, value):
    if not isinstance(value, dict):
        raise GateError("%s must be an object with optional 'model' and 'effort'." % path)
    extra = set(value) - {"model", "effort"}
    if extra:
        raise GateError("%s: unknown key(s) %s (allowed: model, effort)."
                        % (path, ", ".join(sorted(extra))))
    model = value.get("model")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise GateError("%s.model must be a non-empty string (an alias, a model id or "
                        "'inherit')." % path)
    effort = value.get("effort")
    if effort is not None and effort not in EFFORTS:
        raise GateError("%s.effort: unknown value %r (allowed: %s)."
                        % (path, effort, ", ".join(EFFORTS)))


def resolve(settings, skill, role):
    """{"model", "effort"} for one agent; a field that inherits is None."""
    entry = (((settings or {}).get("models") or {}).get(skill) or {}).get(role) or {}
    out = {}
    for key in ("model", "effort"):
        value = entry.get(key) if isinstance(entry, dict) else None
        out[key] = None if value in (None, INHERIT) else value
    return out


def schema_fragment(root=None):
    """The JSON Schema `models` property, derived from the shipped agents.
    schemas/settings.schema.json carries this verbatim; a test compares them."""
    agent = {"type": "object",
             "properties": {"model": {"type": "string", "minLength": 1},
                            "effort": {"enum": list(EFFORTS)}},
             "additionalProperties": False}
    return {
        "description": "Model and effort per subagent, keyed skill -> role. An absent "
                       "skill, role or field, or the value 'inherit', inherits the "
                       "parent session's value. A model is an alias, a full model id "
                       "or 'inherit'. Written in full by `acs settings scaffold`.",
        "type": "object",
        "properties": {
            skill: {"type": "object",
                    "properties": {role: agent for role in roles},
                    "additionalProperties": False}
            for skill, roles in inventory(root).items()},
        "additionalProperties": False}


def covered_roles():
    """Every role the scaffold has a value for; `test_every_role_is_scaffolded`
    compares it with ROLE_KINDS."""
    return sorted(_RECOMMENDED)


assert set(_RECOMMENDED) <= set(ROLE_KINDS), "scaffold names a role acs does not spawn"
