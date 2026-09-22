"""acs_lib.skills — which skills exist, and what each one declares.

Replaces `acs_lib.phases` and the `workflows/phases.yaml` registry it read.
The registry was the fifth central list of the skills — after
`pipeline-state.schema.json`'s 18-name enum, `skill-state.schema.json`'s
33-name enum and the two `argparse` copies in `acs start` / `acs finish` — and
removing those four while keeping the one they were copies of would have
missed the point. So a skill is now described by its own directory:

  skills/<name>/SKILL.md      the skill EXISTS
  skills/<name>/acs.yaml      what acs knows about it (optional)
  agents/<name>-<role>.md     it owns that subagent role

`acs.yaml` is acs's file, not Claude Code's: `SKILL.md` front matter stays the
four keys Claude Code reads (`name`, `description`, `argument-hint`,
`disallowed-tools`) and acs adds nothing to it.

  # skills/create-api-contract/acs.yaml
  phase: build
  reads:
    required: [plan]
    optional: []
  writes: [api-contract]

  # skills/code-standard/acs.yaml
  phase: build
  leg_of: code

`reads` / `writes` name ARTIFACTS, not skills, and they are facts about the
skill that hold in every workflow — which is what lets `acs workflow validate`
check a step list's order without any edge in the workflow file, and lets the
runtime input gate consult the same declaration (§2.1, §2.4 of
docs/REDESIGN-IMPLEMENTATION-PIPELINE.md). A skill that declares neither is
not a step candidate: `setup`, `metrics`, `handoff` and `ship` itself are
skills, not steps, and that is the whole admission rule.

`ship.yaml` alone may be overridden by the consumer repo; the skills are the
plugin's own and have no override, which is why `skills_dir` takes a plugin
root and `resolve_workflow` takes a checkout root.
"""

import os

from ._common import WorkflowError, plugin_root, read_json
from . import schemasubset
from . import yamlsubset
from .yamlsubset import YamlSubsetError

WORKFLOWS_DIRNAME = "workflows"
SKILLS_DIRNAME = "skills"
AGENTS_DIRNAME = "agents"
SKILL_DOC_FILENAME = "SKILL.md"
SKILL_MANIFEST_FILENAME = "acs.yaml"
SHIP_FILENAME = "ship.yaml"
#: A consumer override replaces the plugin's ship.yaml wholesale.
OVERRIDE_WORKFLOW_RELPATH = os.path.join(".acs", "workflows", "ship.yaml")
WORKFLOW_SCHEMA_FILENAME = "workflow.schema.json"
SKILL_SCHEMA_FILENAME = "acs-skill.schema.json"

#: The five lifecycle groups `phase:` may name. Nothing branches on these any
#: more -- they order the README table and group the metrics, and that is all.
PHASE_GROUPS = ("design", "build", "test", "ship", "utility")

#: The subagent roles a skill may own, as `agents/<skill>-<role>.md`.
#: `lens` and `adjudicator` are /acs:review-code's two roles (§3.6): the lens
#: raises candidate findings, the adjudicator tries to refute one.
AGENT_ROLES = ("planner", "executor", "verifier", "lens", "adjudicator")

#: A skill's own failures ARE workflow failures: a step list and the skills it
#: names are two halves of one contract, and a caller that catches one should
#: not have to know which half it read.
SkillsError = WorkflowError


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def workflows_dir(root=None):
    return os.path.join(root or plugin_root(), WORKFLOWS_DIRNAME)


def skills_dir(root=None):
    """The plugin's skills/ tree. Always the plugin's own, never a consumer
    override: the skills ship with the plugin, only ship.yaml is overridable."""
    return os.path.join(root or plugin_root(), SKILLS_DIRNAME)


def agents_dir(root=None):
    return os.path.join(root or plugin_root(), AGENTS_DIRNAME)


def skill_dir(skill, root=None):
    return os.path.join(skills_dir(root), skill)


def manifest_path(skill, root=None):
    return os.path.join(skill_dir(skill, root), SKILL_MANIFEST_FILENAME)


def default_workflow_path(root=None):
    return os.path.join(workflows_dir(root), SHIP_FILENAME)


def override_workflow_path(checkout_root):
    return os.path.join(checkout_root, OVERRIDE_WORKFLOW_RELPATH)


def schema_path(name, root=None):
    return os.path.join(root or plugin_root(), "schemas", name)


def load_schema(name):
    schema = read_json(schema_path(name))
    if not isinstance(schema, dict):
        raise SkillsError("cannot read the schema at %s" % schema_path(name))
    return schema


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def registered_skills(root=None):
    """Every skill that ships, sorted. A skill exists when its directory holds
    a SKILL.md -- there is no list to keep in step with the tree."""
    base = skills_dir(root)
    if not os.path.isdir(base):
        return []
    return sorted(name for name in os.listdir(base)
                  if os.path.isfile(os.path.join(base, name, SKILL_DOC_FILENAME)))


def is_skill(skill, root=None):
    return os.path.isfile(os.path.join(skill_dir(skill, root), SKILL_DOC_FILENAME))


def load_manifest(skill, root=None):
    """`skills/<skill>/acs.yaml`, schema-checked, normalised. `{}` when the
    skill declares none -- a skill with no manifest is a skill acs knows
    nothing about beyond its existence, which is a legitimate thing to be."""
    path = manifest_path(skill, root)
    if not os.path.isfile(path):
        return {}
    try:
        doc, lines = yamlsubset.parse_file(path)
    except YamlSubsetError as exc:
        raise SkillsError(exc.reason, path=exc.path, line=exc.line)
    if doc is None:
        return {}
    errors = schemasubset.schema_errors(load_schema(SKILL_SCHEMA_FILENAME), doc)
    if errors:
        node, message = errors[0]
        raise SkillsError("%s: %s" % (schemasubset.pointer(node), message),
                          path=path, line=yamlsubset.line_for(lines, node))
    reads = doc.get("reads") or {}
    doc["reads"] = {
        "required": list(reads.get("required") or []),
        "optional": list(reads.get("optional") or []),
    }
    doc["writes"] = list(doc.get("writes") or [])
    return doc


def load_manifests(root=None):
    """{skill: manifest} for every skill that ships. One pass over the tree,
    for callers that would otherwise read the same files once per question."""
    return dict((skill, load_manifest(skill, root)) for skill in registered_skills(root))


# ---------------------------------------------------------------------------
# What a skill declares
# ---------------------------------------------------------------------------

def phase_of(skill, manifests=None, root=None):
    """The lifecycle group a skill belongs to, else None. A leg reports the
    group of the entry point a user actually runs."""
    manifests = manifests if manifests is not None else load_manifests(root)
    entry = (manifests.get(skill) or {}).get("leg_of")
    if entry:
        skill = entry
    return (manifests.get(skill) or {}).get("phase")


def entry_point_of(skill, manifests=None, root=None):
    """The entry point an internal leg serves, else None. A user-facing skill
    is nobody's leg."""
    manifests = manifests if manifests is not None else load_manifests(root)
    return (manifests.get(skill) or {}).get("leg_of")


def legs_of(skill, manifests=None, root=None):
    """The legs that name `skill` as their entry point, sorted."""
    manifests = manifests if manifests is not None else load_manifests(root)
    return sorted(leg for leg, doc in manifests.items() if (doc or {}).get("leg_of") == skill)


def skill_legs(manifests=None, root=None):
    """{leg: entry-point} -- a skill that keeps its SKILL.md, agents, hooks and
    gate and stays Skill-invocable, but whose only user-facing command is the
    entry point it serves."""
    manifests = manifests if manifests is not None else load_manifests(root)
    return dict((leg, doc["leg_of"]) for leg, doc in manifests.items()
                if (doc or {}).get("leg_of"))


def reads_of(skill, manifests=None, root=None):
    """(required, optional) artifact names this skill reads."""
    manifests = manifests if manifests is not None else load_manifests(root)
    reads = (manifests.get(skill) or {}).get("reads") or {}
    return list(reads.get("required") or []), list(reads.get("optional") or [])


def writes_of(skill, manifests=None, root=None):
    """The artifact names this skill writes."""
    manifests = manifests if manifests is not None else load_manifests(root)
    return list((manifests.get(skill) or {}).get("writes") or [])


def is_step_candidate(skill, manifests=None, root=None):
    """True when a workflow may name this skill as a step: it declares what it
    reads or what it writes, and it is not a leg of another skill."""
    manifests = manifests if manifests is not None else load_manifests(root)
    doc = manifests.get(skill) or {}
    if doc.get("leg_of"):
        return False
    required, optional = reads_of(skill, manifests)
    return bool(required or optional or writes_of(skill, manifests))


def step_candidates(manifests=None, root=None):
    """Every skill a workflow may name as a step, sorted."""
    manifests = manifests if manifests is not None else load_manifests(root)
    return sorted(s for s in manifests if is_step_candidate(s, manifests))


# ---------------------------------------------------------------------------
# Agents, by naming convention
# ---------------------------------------------------------------------------

def agent_roles_of(skill, root=None):
    """The subagent roles `skill` owns, in AGENT_ROLES order -- read from the
    tree (`agents/<skill>-<role>.md`), never from a declaration that could
    drift from it. `[]` when it owns none, which is the right answer for a
    mechanical action or a dispatcher."""
    base = agents_dir(root)
    return [role for role in AGENT_ROLES
            if os.path.isfile(os.path.join(base, "%s-%s.md" % (skill, role)))]


def skill_agents(root=None):
    """{skill: [role, ...]} for every skill that owns at least one agent."""
    out = {}
    for skill in registered_skills(root):
        roles = agent_roles_of(skill, root)
        if roles:
            out[skill] = roles
    return out


def agent_files(root=None):
    """Every agents/*.md basename (no extension), sorted."""
    base = agents_dir(root)
    if not os.path.isdir(base):
        return []
    return sorted(n[:-3] for n in os.listdir(base) if n.endswith(".md"))


def unreachable_agents(root=None):
    """Agent files whose `<skill>-<role>` name does not resolve to a skill that
    ships and a role acs spawns. PRD G8 -- every agent file is reachable --
    is this list being empty, checked by naming convention rather than by
    keeping a registry in step with the tree."""
    known = set(registered_skills(root))
    bad = []
    for name in agent_files(root):
        skill, _, role = name.rpartition("-")
        if role not in AGENT_ROLES or skill not in known:
            bad.append(name)
    return bad
