"""acs_lib.agent_sync — turn `settings.models` into the agents that run.

A plugin agent (`acs:<skill>-<role>`) cannot be overridden from a project: a
same-named project agent loses to it and the `acs:` namespace is the plugin's
alone. A subagent's model and effort are set by its frontmatter, and effort has
no per-call form. So for each agent whose settings entry sets a real value,
`sync` writes a plain-named copy -- `.claude/agents/acs-<skill>-<role>.md` --
whose frontmatter carries that `model:` and `effort:`, and a coordinator spawns
that copy instead of the plugin's.

The copy is the plugin agent's own file, renamed, with the two fields set and a
marker line carrying a digest of what it was built from. `sync` rewrites it when
the plugin's prompt or the settings change, and removes a marked copy whose
entry no longer sets anything. A file without the marker is never touched.

`acs-<skill>-<role>` agents are acs's own as much as the plugin's: the
lifecycle hooks match `^acs[:-]` and read the role from either spelling.
"""

import hashlib
import os

from . import models
from .skills import agents_dir, entry_point_of, split_agent_name

#: Spelling of a generated copy's name and of the plugin agent's.
GENERATED_PREFIX = "acs-"
PLUGIN_PREFIX = "acs:"

MARKER_PREFIX = "<!-- acs:generated "

#: Where a project's agents live, relative to the checkout root.
PROJECT_AGENTS_PARTS = (".claude", "agents")


def generated_name(agent):
    return GENERATED_PREFIX + agent


def plugin_name(agent):
    return PLUGIN_PREFIX + agent


def project_agents_dir(project_root):
    return os.path.join(project_root, *PROJECT_AGENTS_PARTS)


def _split_frontmatter(text):
    """(frontmatter_lines, body) of an agent file; the frontmatter is the lines
    between the first two `---` lines. (None, text) when there is none."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1:])
    return None, text


def _key(line):
    head = line.split(":", 1)[0] if ":" in line else ""
    return head.strip() if head and not head.startswith((" ", "\t")) else None


def render(source_text, agent, values):
    """The generated copy of `source_text` for `agent` with `values` set, or
    None when `values` sets nothing (the plugin agent is spawned as it is)."""
    values = {k: v for k, v in (values or {}).items() if v}
    if not values:
        return None
    front, body = _split_frontmatter(source_text)
    if front is None:
        return None
    kept = []
    for line in front:
        key = _key(line)
        if key == "name":
            kept.append("name: %s" % generated_name(agent))
        elif key in ("model", "effort"):
            continue
        else:
            kept.append(line)
    for field in ("model", "effort"):
        if field in values:
            kept.append("%s: %s" % (field, values[field]))
    content = "---\n%s\n---\n%s" % ("\n".join(kept), body)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    marker = "%sfrom=%s sha=%s -->" % (MARKER_PREFIX, agent, digest)
    head, _sep, rest = content.partition("\n---\n")
    return "%s\n---\n%s\n%s" % (head, marker, rest.lstrip("\n"))


def _is_generated(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return MARKER_PREFIX in fh.read(4096)
    except OSError:
        return False


def expected(settings, plugin_root=None):
    """{generated_name: rendered text} for every agent whose entry sets a value."""
    out = {}
    base = agents_dir(plugin_root)
    for skill, roles in models.inventory(plugin_root).items():
        for role in roles:
            agent = "%s-%s" % (skill, role)
            values = models.resolve(settings, skill, role)
            if not any(values.values()):
                continue
            with open(os.path.join(base, agent + ".md"), encoding="utf-8") as fh:
                text = render(fh.read(), agent, values)
            if text:
                out[generated_name(agent)] = text
    return out


def sync(settings, project_root, plugin_root=None, dry_run=False):
    """Make `.claude/agents/acs-*.md` match `settings.models`.

    Returns {"written": [...], "removed": [...], "unchanged": [...]} of
    generated agent names. Only marked files are ever replaced or removed."""
    want = expected(settings, plugin_root)
    target = project_agents_dir(project_root)
    out = {"written": [], "removed": [], "unchanged": []}
    for name, text in sorted(want.items()):
        path = os.path.join(target, name + ".md")
        try:
            with open(path, encoding="utf-8") as fh:
                current = fh.read()
        except OSError:
            current = None
        if current == text:
            out["unchanged"].append(name)
            continue
        if current is not None and MARKER_PREFIX not in current[:4096]:
            continue  # a person's own file by that name: never overwritten
        out["written"].append(name)
        if not dry_run:
            os.makedirs(target, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
    if os.path.isdir(target):
        for fname in sorted(os.listdir(target)):
            stem = fname[:-3] if fname.endswith(".md") else None
            if not stem or not stem.startswith(GENERATED_PREFIX) or stem in want:
                continue
            path = os.path.join(target, fname)
            if _is_generated(path):
                out["removed"].append(stem)
                if not dry_run:
                    os.remove(path)
    return out


def skill_for_step(step):
    """The skill whose agents a step spawns: a delivery-path leg spawns its
    entry point's agents, any other step its own."""
    return entry_point_of(step) or step


def spawn_names(settings, skill, plugin_root=None):
    """{role: agent name to spawn} for `skill`: the generated copy where its
    entry sets a value, else the plugin agent."""
    out = {}
    for role in models.inventory(plugin_root).get(skill, []):
        agent = "%s-%s" % (skill, role)
        values = models.resolve(settings, skill, role)
        out[role] = generated_name(agent) if any(values.values()) else plugin_name(agent)
    return out


def agent_name_parts(agent_type):
    """(skill, role) of either spelling (`acs:x-y` or `acs-x-y`), else (None, None)."""
    if not isinstance(agent_type, str):
        return None, None
    for prefix in (PLUGIN_PREFIX, GENERATED_PREFIX):
        if agent_type.startswith(prefix):
            return split_agent_name(agent_type[len(prefix):])
    return None, None


def sync_for_step(settings, project_root, step, plugin_root=None):
    """What `acs step start` reports: the names a coordinator spawns for
    `step`'s skill, after making the generated copies match the settings.

    {"agents": {role: name}, "sync": {...} | None, "error": str | None}. A sync
    that fails is reported, not fatal -- the fallback is the plugin's own agents,
    which inherit -- so the names fall back with it."""
    skill = skill_for_step(step)
    try:
        result = sync(settings, project_root, plugin_root)
        return {"agents": spawn_names(settings, skill, plugin_root),
                "sync": result, "error": None}
    except OSError as exc:
        return {"agents": spawn_names({}, skill, plugin_root), "sync": None,
                "error": "agent sync failed (%s); spawning the plugin's agents, which inherit" % exc}


def with_spawn_names(obj, settings, plugin_root=None):
    """`obj` with every `agent` field naming a plugin agent (`acs:<skill>-<role>`)
    rewritten to the name to spawn. For a controller that prints the agent per
    action (analysis_loop) instead of leaving the coordinator to look it up."""
    if isinstance(obj, list):
        return [with_spawn_names(item, settings, plugin_root) for item in obj]
    if not isinstance(obj, dict):
        return obj
    out = {}
    for key, value in obj.items():
        if key == "agent" and isinstance(value, str) and value.startswith(PLUGIN_PREFIX):
            skill, role = split_agent_name(value[len(PLUGIN_PREFIX):])
            if skill:
                value = spawn_names(settings, skill, plugin_root).get(role, value)
        else:
            value = with_spawn_names(value, settings, plugin_root)
        out[key] = value
    return out
