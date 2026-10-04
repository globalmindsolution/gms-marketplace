"""acs_lib.skills — which skills exist, and which subagents each one owns.

A skill is described by its own directory and nothing else:

  skills/<name>/SKILL.md      the skill EXISTS
  agents/<name>-<role>.md     it owns that subagent role

There is no per-skill manifest. Each skill is an independent skill: it reads
what it finds, falls back to the run's subject when an upstream artifact is
absent, and runs the same whether `/acs:ship` invoked it or a user did. The
workflow (`workflows/ship.yaml`) is only an orchestrator that keeps the ORDER
of the skills it names; it asks nothing of a skill beyond that the skill
ships. So nothing here declares what a skill reads or writes, and no gate
refuses a skill because an earlier one has not run.

Subagents are per skill, named for what they do (`create-prd-surveyor`,
`create-impl-plan-plan-reviewer`, `review-code-adjudicator`), and a skill owns
only the roles its own logic needs -- a mechanical skill owns none. What the
hooks need to know about a role is its KIND, in ROLE_KINDS:

  survey   reads the repo and records notes and questions; writes only its
           own workspace files
  write    produces the deliverable -- the repo, or the workspace draft. The
           executor file-map guard applies while a `write` agent runs
  judge    re-derives and judges fresh; read-only by charter

The kind also picks the model tier a role runs on from `settings.models`
(`planner` / `executor` / `verifier`), so a new role needs one line here and
no new settings key.

`ship.yaml` alone may be overridden by the consumer repo; the skills are the
plugin's own and have no override, which is why `skills_dir` takes a plugin
root and `resolve_workflow` takes a checkout root.
"""

import os

from ._common import LEG_ENTRY_POINTS, WorkflowError, plugin_root, read_json

WORKFLOWS_DIRNAME = "workflows"
SKILLS_DIRNAME = "skills"
AGENTS_DIRNAME = "agents"
SKILL_DOC_FILENAME = "SKILL.md"
SHIP_FILENAME = "ship.yaml"
#: A consumer override replaces the plugin's ship.yaml wholesale.
OVERRIDE_WORKFLOW_RELPATH = os.path.join(".acs", "workflows", "ship.yaml")
WORKFLOW_SCHEMA_FILENAME = "workflow.schema.json"

#: The three things a subagent can be. See the module docstring.
ROLE_KIND_NAMES = ("survey", "write", "judge")

#: Every subagent role acs spawns -> its kind. A role name may be shared by
#: several skills (`reviewer`, `author`); the agent FILE is always per skill.
ROLE_KINDS = {
    # survey -- read-only on the repo, writes its notes into the workspace
    "surveyor": "survey",
    "impact-analyst": "survey",
    # write -- produces the deliverable
    "analyst": "write",
    "author": "write",
    "architect": "write",
    "designer": "write",
    "planner": "write",
    "contract-author": "write",
    "test-designer": "write",
    "implementer": "write",
    "test-writer": "write",
    "doc-updater": "write",
    # judge -- read-only, re-derives and judges fresh
    "reviewer": "judge",
    "impact-reviewer": "judge",
    "design-reviewer": "judge",
    "plan-reviewer": "judge",
    "contract-reviewer": "judge",
    "trace-reviewer": "judge",
    "suite-runner": "judge",
    "drift-reviewer": "judge",
    "lens": "judge",
    "adjudicator": "judge",
}

#: Every role acs spawns, in a stable order.
AGENT_ROLES = tuple(sorted(ROLE_KINDS))


#: {leg: entry point}. A leg keeps its SKILL.md and stays Skill-invocable, but
#: a workflow never names it -- its entry point dispatches to it. The legs are
#: `code`'s four delivery paths, which run under `code`'s gate and state
#: (`LEG_ENTRY_POINTS`).
SKILL_LEGS = dict(LEG_ENTRY_POINTS)

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


def entry_point_of(skill):
    """The entry point an internal leg serves, else None. A user-facing skill
    is nobody's leg."""
    return SKILL_LEGS.get(skill)


def legs_of(skill):
    """The legs that name `skill` as their entry point, sorted."""
    return sorted(leg for leg, entry in SKILL_LEGS.items() if entry == skill)


def skill_legs():
    """{leg: entry-point}."""
    return dict(SKILL_LEGS)


# ---------------------------------------------------------------------------
# Agents, by naming convention
# ---------------------------------------------------------------------------

def role_kind(role):
    """`survey`, `write` or `judge` for a role acs spawns, else None."""
    return ROLE_KINDS.get(role)


def split_agent_name(name, skills=None):
    """(skill, role) for an agent name `<skill>-<role>`, else (None, None).

    Both halves may contain hyphens (`create-impl-plan-plan-reviewer`), so the
    split is not positional: the skill is the LONGEST shipped skill name the
    agent name starts with, and the rest must be a role acs spawns. Longest
    first, because `code` is a prefix of `code-small`."""
    if not isinstance(name, str):
        return None, None
    skills = skills if skills is not None else registered_skills()
    for skill in sorted(skills, key=len, reverse=True):
        prefix = skill + "-"
        if name.startswith(prefix) and name[len(prefix):] in ROLE_KINDS:
            return skill, name[len(prefix):]
    return None, None


def agent_files(root=None):
    """Every agents/*.md basename (no extension), sorted."""
    base = agents_dir(root)
    if not os.path.isdir(base):
        return []
    return sorted(n[:-3] for n in os.listdir(base) if n.endswith(".md"))


def skill_agents(root=None):
    """{skill: [role, ...]} for every skill that owns at least one agent --
    read from the tree (`agents/<skill>-<role>.md`), never from a declaration
    that could drift from it. Roles in AGENT_ROLES order."""
    skills = registered_skills(root)
    out = {}
    for name in agent_files(root):
        skill, role = split_agent_name(name, skills)
        if skill:
            out.setdefault(skill, []).append(role)
    return dict((skill, sorted(roles, key=AGENT_ROLES.index))
                for skill, roles in out.items())


def agent_roles_of(skill, root=None):
    """The subagent roles `skill` owns. `[]` when it owns none, which is the
    right answer for a mechanical action or a dispatcher."""
    return skill_agents(root).get(skill, [])


def unreachable_agents(root=None):
    """Agent files whose name does not resolve to a skill that ships and a
    role acs spawns. PRD G8 -- every agent file is reachable -- is this list
    being empty, checked by naming convention rather than by keeping a
    registry in step with the tree."""
    skills = registered_skills(root)
    return [name for name in agent_files(root)
            if split_agent_name(name, skills) == (None, None)]
