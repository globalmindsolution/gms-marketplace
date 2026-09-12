"""acs_lib.workflow — the declarative delivery pipeline.

Until the skills-independence refactor, /acs:ship carried the pipeline order in
prose and acs_lib.gates refused a skill until its predecessor had completed.
The order now lives in `workflows/ship.yaml` (a consumer may replace it
wholesale with `<repo>/.acs/workflows/ship.yaml`), skills are grouped into
phases by `workflows/phases.yaml`, and /acs:ship is a loop over `acs.py
workflow next`. This module owns all of that:

  load_phases / allowed_ship_skills   the registry (phases, aliases, internal
                                      legs) and the ship-eligible subset
  resolve / load_workflow / validate  override-or-default resolution, schema
                                      (a stdlib subset of JSON Schema, since
                                      hooks may not import jsonschema) and the
                                      semantic checks: ids unique, needs name
                                      EARLIER steps, stop_after exists,
                                      predicates known, DAG acyclic
  PREDICATES                          the four named, pure predicates the
                                      `when` / `requires` keys may name
  next_steps                          the walk: which steps are READY for a
                                      ticket given pipeline-state.json, in
                                      `single` or `parallel` mode
  pending_needs                       what a hand-invoked skill's predecessors
                                      look like (the pre-hook advisory reads it)

Gates stay INPUT and SAFETY checks; nothing here refuses a skill for running
out of order. Every ledger read goes through acs_lib.state; ticket documents
are read through the acs_lib facade so the docs-tree reader, when it lands,
is honoured without an import here.
"""

import importlib
import os
import re

from ._common import GateError, plugin_root, read_json
from .repo import find_ticket_partition
from .state import load_pipeline, skill_completed, update_pipeline
from . import yamlsubset
from .yamlsubset import YamlSubsetError

WORKFLOWS_DIRNAME = "workflows"
SKILLS_DIRNAME = "skills"
PHASES_FILENAME = "phases.yaml"
SHIP_FILENAME = "ship.yaml"
#: The consumer override, relative to the checkout root; replaces the default wholesale.
OVERRIDE_WORKFLOW_RELPATH = os.path.join(".acs", "workflows", "ship.yaml")
SHIP_SCHEMA_FILENAME = "ship-workflow.schema.json"
PHASES_SCHEMA_FILENAME = "phases.schema.json"

PHASE_GROUPS = ("design", "build", "test", "ship", "utility")
#: The phases ship.yaml may draw steps from...
SHIP_PHASES = ("build", "test", "ship")
#: ...minus the two ship-phase skills a human always drives.
SHIP_EXCLUDED_SKILLS = ("merge-pr", "release")
BOUNDARIES = ("full_verify_stop",)
DEFAULT_STOP_AFTER = "create-pr"
DEFAULT_MAX_PARALLEL = 2
#: A step with one of these ledger statuses counts as satisfied for its dependants.
SATISFIED_STATUSES = ("completed", "skipped")
SKIPPED_STATUS = "skipped"
#: A needed step in any of these states is simply READY again (re-run).
RERUN_STATUSES = ("failed", "interrupted", "in_progress", "handed_off")


class WorkflowError(GateError):
    """A workflow file outside its contract, or a walk that cannot proceed.
    `line`/`path` locate a file problem; `payload` is the JSON a CLI emits
    before exiting 2 (the epic refusal)."""

    def __init__(self, reason, path=None, line=None, payload=None):
        self.reason = reason
        self.path = path
        self.line = line
        self.payload = payload
        super().__init__(self.render())

    def render(self):
        where = self.path or ""
        if self.line:
            where = "%s:%d" % (where, self.line) if where else "line %d" % self.line
        return "%s: %s" % (where, self.reason) if where else self.reason


def _lib():
    """The acs_lib facade, resolved at call time: load_ticket and
    design_requirement are looked up through it so a module that later takes
    them over (the docs-tree artifacts reader) is honoured, and so gates --
    which will import this module for its advisory -- is never imported here."""
    return importlib.import_module(__package__ or "acs_lib")


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


# ---------------------------------------------------------------------------
# A stdlib subset of JSON Schema (draft 2020-12 keywords the two workflow
# schemas use). Hooks are stdlib-only; the tests cross-check the same schemas
# with the jsonschema package so the subset cannot drift from the real thing.
# ---------------------------------------------------------------------------

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is_type(value, typ):
    if isinstance(typ, list):
        return any(_is_type(value, t) for t in typ)
    if typ == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if typ == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[typ])


def _type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    for name, cls in (("object", dict), ("array", list), ("string", str), ("integer", int)):
        if isinstance(value, cls):
            return name
    return type(value).__name__


def _equal(a, b):
    """JSON equality: a boolean never equals an integer, unlike Python."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    return a == b


def _deref(root, ref):
    if not ref.startswith("#/"):
        raise WorkflowError("unsupported $ref %r in schema" % ref)
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _schema_errors(schema, value, root=None, path=()):
    """[(path, message)] for every violation, in traversal order."""
    root = schema if root is None else root
    if "$ref" in schema:
        schema = _deref(root, schema["$ref"])
    typ = schema.get("type")
    if typ and not _is_type(value, typ):
        return [(path, "expected %s, got %s" % (typ if isinstance(typ, str) else "/".join(typ),
                                                  _type_name(value)))]
    errors = []
    if "const" in schema and not _equal(value, schema["const"]):
        errors.append((path, "must be %r" % (schema["const"],)))
    if "enum" in schema and not any(_equal(value, e) for e in schema["enum"]):
        errors.append((path, "%r is not one of %s" % (value, ", ".join(repr(e) for e in schema["enum"]))))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append((path + (key,), "missing required key %r" % key))
        props = schema.get("properties", {})
        for key, item in value.items():
            if key in props:
                errors.extend(_schema_errors(props[key], item, root, path + (key,)))
            elif schema.get("additionalProperties") is False:
                errors.append((path + (key,), "unknown key %r" % key))
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(_schema_errors(schema["additionalProperties"], item, root, path + (key,)))
            if "propertyNames" in schema:
                errors.extend(_schema_errors(schema["propertyNames"], key, root, path + (key,)))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append((path, "needs at least %d item(s)" % schema["minItems"]))
        if schema.get("uniqueItems") and len({repr(v) for v in value}) != len(value):
            errors.append((path, "items must be unique"))
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(_schema_errors(schema["items"], item, root, path + (index,)))
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append((path, "must not be empty"))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append((path, "%r does not match %s" % (value, schema["pattern"])))
    if _is_type(value, "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append((path, "must be >= %s" % schema["minimum"]))
    if "oneOf" in schema:
        matches = sum(1 for sub in schema["oneOf"] if not _schema_errors(sub, value, root, path))
        if matches != 1:
            errors.append((path, "%r does not match exactly one of the allowed forms" % (value,)))
    return errors


def _pointer(path):
    out = ""
    for part in path:
        out += "[%d]" % part if isinstance(part, int) else (".%s" % part if out else str(part))
    return out or "(document)"


def _load_schema(name):
    schema = read_json(schema_path(name))
    if not isinstance(schema, dict):
        raise WorkflowError("cannot read the schema at %s" % schema_path(name))
    return schema


# ---------------------------------------------------------------------------
# Phases registry
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
        raise WorkflowError(exc.reason, path=exc.path, line=exc.line)
    errors = _schema_errors(_load_schema(PHASES_SCHEMA_FILENAME), doc)
    if errors:
        node, message = errors[0]
        raise WorkflowError("%s: %s" % (_pointer(node), message), path=path,
                            line=yamlsubset.line_for(lines, node))
    seen = {}
    for group in PHASE_GROUPS:
        for skill in doc["phases"][group]:
            if skill in seen:
                raise WorkflowError("skill %r is listed under both %s and %s" % (skill, seen[skill], group),
                                    path=path, line=yamlsubset.line_for(lines, ("phases", group)))
            seen[skill] = group
    aliases = doc.get("aliases") or {}
    for alias, target in aliases.items():
        if alias in seen:
            raise WorkflowError("alias %r is also a registered skill" % alias, path=path,
                                line=yamlsubset.line_for(lines, ("aliases", alias)))
        if target not in seen:
            raise WorkflowError("alias %r points at unregistered skill %r" % (alias, target), path=path,
                                line=yamlsubset.line_for(lines, ("aliases", alias)))
    doc["aliases"] = aliases
    internal = doc.get("internal") or {}
    for leg, entry in internal.items():
        line = yamlsubset.line_for(lines, ("internal", leg))
        if leg in seen:
            raise WorkflowError("internal leg %r is also a registered skill" % leg, path=path, line=line)
        if leg in aliases:
            raise WorkflowError("internal leg %r is also an alias" % leg, path=path, line=line)
        if entry in internal:
            raise WorkflowError("internal leg %r points at %r, which is itself an internal leg" % (leg, entry),
                                path=path, line=line)
        if entry not in seen:
            raise WorkflowError("internal leg %r points at unregistered entry point %r" % (leg, entry),
                                path=path, line=line)
    for leg in internal:
        if not os.path.isdir(os.path.join(skills_dir(), leg)):
            raise WorkflowError("internal leg %r has no skills/%s directory" % (leg, leg), path=path,
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
    """The skills a ship.yaml step may name: build + test + ship, minus
    SHIP_EXCLUDED_SKILLS. The schema's `skill` enum mirrors this list."""
    phases = phases or load_phases()
    return [skill for group in SHIP_PHASES for skill in phases["phases"][group]
            if skill not in SHIP_EXCLUDED_SKILLS]


# ---------------------------------------------------------------------------
# ship.yaml: resolution and validation
# ---------------------------------------------------------------------------

def load_workflow(path):
    """(doc, lines) for a workflow file; parse failures become WorkflowError."""
    try:
        return yamlsubset.parse_file(path)
    except YamlSubsetError as exc:
        raise WorkflowError(exc.reason, path=exc.path, line=exc.line)


def resolve_workflow(checkout_root, plugin=None):
    """{source: "override"|"default", path, workflow}: the consumer's
    .acs/workflows/ship.yaml when present, else the plugin default. Parsed,
    not validated -- see validate_workflow_file."""
    override = override_workflow_path(checkout_root) if checkout_root else None
    if override and os.path.isfile(override):
        source, path = "override", override
    else:
        source, path = "default", default_workflow_path(plugin)
    doc, _lines = load_workflow(path)
    return {"source": source, "path": path, "workflow": doc}


def _fail(reason, path, lines, node):
    raise WorkflowError(reason, path=path, line=yamlsubset.line_for(lines or {}, node))


def validate_workflow(doc, phases=None, lines=None, path=None):
    """Schema plus semantic checks; returns `doc`, raises WorkflowError naming
    the source line when `lines` (from yamlsubset.parse) is given."""
    phases = phases or load_phases()
    errors = _schema_errors(_load_schema(SHIP_SCHEMA_FILENAME), doc)
    if errors:
        node, message = errors[0]
        _fail("%s: %s" % (_pointer(node), message), path, lines, node)
    allowed = allowed_ship_skills(phases)
    steps = doc["steps"]
    ids = []
    for index, step in enumerate(steps):
        node = ("steps", index)
        if step["id"] in ids:
            _fail("steps[%d].id: duplicate step id %r" % (index, step["id"]), path, lines, node + ("id",))
        ids.append(step["id"])
    for index, step in enumerate(steps):
        node = ("steps", index)
        if step["skill"] not in allowed:
            _fail("steps[%d].skill: %r is not a build/test/ship skill (allowed: %s)"
                  % (index, step["skill"], ", ".join(allowed)), path, lines, node + ("skill",))
        for need in step.get("needs") or []:
            if need not in ids[:index]:
                _fail("steps[%d].needs: %r must name an EARLIER step" % (index, need),
                      path, lines, node + ("needs",))
        for key in ("when", "requires"):
            if key in step and step[key] not in PREDICATES:
                _fail("steps[%d].%s: unknown predicate %r (known: %s)"
                      % (index, key, step[key], ", ".join(sorted(PREDICATES))), path, lines, node + (key,))
        on_fail = step.get("on_fail")
        if on_fail:
            if on_fail["relay_to"] not in ids or on_fail["relay_to"] == step["id"]:
                _fail("steps[%d].on_fail.relay_to: %r is not another step id" % (index, on_fail["relay_to"]),
                      path, lines, node + ("on_fail", "relay_to"))
            loops = on_fail.get("max_loops")
            if isinstance(loops, str) and loops not in MAX_LOOPS_NAMES:
                _fail("steps[%d].on_fail.max_loops: unknown name %r (known: %s)"
                      % (index, loops, ", ".join(sorted(MAX_LOOPS_NAMES))), path, lines,
                      node + ("on_fail", "max_loops"))
        if "on_replan" in step and (step["on_replan"] not in ids or step["on_replan"] == step["id"]):
            _fail("steps[%d].on_replan: %r is not another step id" % (index, step["on_replan"]),
                  path, lines, node + ("on_replan",))
    stop_after = doc.get("stop_after", DEFAULT_STOP_AFTER)
    if stop_after not in ids:
        _fail("stop_after: %r is not a step id" % stop_after, path, lines, ("stop_after",))
    _check_acyclic(steps, path, lines)
    return doc


def _check_acyclic(steps, path, lines):
    """`needs` must name earlier steps, which already rules a cycle out; this
    is the explicit check so the guarantee does not rest on one loop above."""
    needs = {step["id"]: list(step.get("needs") or []) for step in steps}
    state = {}
    for start in needs:
        stack = [(start, iter(needs[start]))]
        state[start] = "open"
        while stack:
            node, it = stack[-1]
            nxt = None
            for candidate in it:
                nxt = candidate
                break
            if nxt is None:
                state[node] = "done"
                stack.pop()
            elif state.get(nxt) == "open":
                _fail("steps: dependency cycle through %r" % nxt, path, lines, ("steps",))
            elif state.get(nxt) is None:
                state[nxt] = "open"
                stack.append((nxt, iter(needs.get(nxt, []))))


def validate_workflow_file(path, phases=None):
    """Parse and validate one file, reporting failures at their line."""
    doc, lines = load_workflow(path)
    return validate_workflow(doc, phases=phases, lines=lines, path=path)


# ---------------------------------------------------------------------------
# Ticket context and artifact locations
# ---------------------------------------------------------------------------

def ticket_context(ctx, ticket_id, tdir=None):
    """A build_context() dict extended with ticket_id, tdir and ticket. Refuses
    an archived, missing or unreadable ticket with a WorkflowError."""
    if tdir is None:
        tdir, archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
        if archived:
            raise WorkflowError("ticket %s is done and archived (%s); nothing left to run"
                                % (ticket_id, tdir))
        if not os.path.isdir(tdir):
            raise WorkflowError("no workspace partition for %s (expected %s) — run /acs:create-ticket first"
                                % (ticket_id, tdir))
    ticket = _lib().load_ticket(tdir)
    if not isinstance(ticket, dict):
        raise WorkflowError("ticket file missing or corrupt under %s — run /acs:create-ticket first" % tdir)
    wctx = dict(ctx)
    wctx.update({"ticket_id": ticket_id, "tdir": tdir, "ticket": ticket})
    return wctx


def _tickets_path(settings):
    artifacts = (settings or {}).get("artifacts") or {}
    return artifacts["tickets_path"] if "tickets_path" in artifacts else "docs/tickets"


def _ticket_docs_dir(settings, checkout_root, ticket_id):
    """<checkout_root>/<artifacts.tickets_path>/<ID>, or None when the docs
    tree is opted out (tickets_path null). Private: acs_lib.artifacts owns the
    public resolver once it lands."""
    base = _tickets_path(settings)
    if not base or not checkout_root:
        return None
    return os.path.join(checkout_root, base, ticket_id)


def ticket_artifact_path(wctx, name, ticket_id=None, tdir=None):
    """Where a ticket artifact (analysis.md, plan.md, design.md, ...) lives:
    the docs-tree folder first, then the workspace partition; None when
    neither has it."""
    ticket_id = ticket_id or wctx["ticket_id"]
    tdir = tdir or wctx["tdir"]
    candidates = []
    docs = _ticket_docs_dir(wctx.get("settings"), wctx.get("checkout_root"), ticket_id)
    if docs:
        candidates.append(os.path.join(docs, name))
    candidates.append(os.path.join(tdir, name))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def _front_matter(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        front, _body = yamlsubset.split_front_matter(text)
    except YamlSubsetError as exc:
        raise WorkflowError("front matter: %s" % exc.reason, path=path, line=exc.line)
    return front or {}


# ---------------------------------------------------------------------------
# Predicates -- pure functions of (ticket, ledger, settings, artifacts)
# ---------------------------------------------------------------------------

def _design_ticket(wctx):
    """(required, design_dir, design_ticket_id) per acs_lib.design_requirement."""
    required, design_dir, source = _lib().design_requirement(wctx, wctx["tdir"], wctx["ticket"])
    if not required:
        return False, None, None
    design_ticket = wctx["ticket_id"] if source == "own" else wctx["ticket"].get("parent")
    return True, design_dir, design_ticket


def design_approved(wctx):
    """True when no design is required (needs_design false, no parent design
    pending), or when the applicable design.md exists and the ledger records
    create-design completed for that ticket."""
    required, design_dir, design_ticket = _design_ticket(wctx)
    if not required:
        return True
    if ticket_artifact_path(wctx, "design.md", ticket_id=design_ticket, tdir=design_dir) is None:
        return False
    return skill_completed(design_dir, "create-design")


def design_pointer(wctx):
    _required, _design_dir, design_ticket = _design_ticket(wctx)
    design_ticket = design_ticket or wctx["ticket_id"]
    if design_ticket != wctx["ticket_id"]:
        return "run /acs:create-design %s (the parent epic) first" % design_ticket
    return "run /acs:create-design %s first" % design_ticket


def api_surface_changed(wctx):
    """analysis.md front matter says `api_surface: true`."""
    path = ticket_artifact_path(wctx, "analysis.md")
    if path is None:
        return False
    return _front_matter(path).get("api_surface") is True


def e2e_configured(wctx):
    settings = wctx.get("settings") or {}
    e2e = settings.get("e2e")
    suite = (settings.get("suites") or {}).get("e2e")
    return bool(isinstance(e2e, dict) and e2e) or bool(isinstance(suite, dict) and suite)


def post_code_test_active(wctx):
    """settings.post_code_test.enabled when set; else whether e2e is configured."""
    enabled = ((wctx.get("settings") or {}).get("post_code_test") or {}).get("enabled")
    if enabled is not None:
        return bool(enabled)
    return e2e_configured(wctx)


def post_code_test_fix_loops_cap(wctx):
    cap = ((wctx.get("settings") or {}).get("post_code_test") or {}).get("fix_loops_cap")
    if isinstance(cap, int) and not isinstance(cap, bool) and cap >= 0:
        return cap
    return 2


PREDICATES = {
    "design_approved": design_approved,
    "api_surface_changed": api_surface_changed,
    "e2e_configured": e2e_configured,
    "post_code_test_active": post_code_test_active,
}
#: The human pointer a `requires` predicate offers when false.
POINTERS = {"design_approved": design_pointer}
#: Names an `on_fail.max_loops` may carry instead of an integer.
MAX_LOOPS_NAMES = {"post_code_test_fix_loops_cap": post_code_test_fix_loops_cap}


def _pointer_for(predicate, wctx):
    render = POINTERS.get(predicate)
    if render:
        return render(wctx)
    return "%s is false for %s" % (predicate, wctx["ticket_id"])


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------

def _ledger_keys(step, aliases):
    """Ledger keys that record this step: its id, its skill (post-hooks write
    the skill name), and any alias directory that forwards to the skill."""
    keys = [step["id"]]
    if step["skill"] not in keys:
        keys.append(step["skill"])
    keys.extend(alias for alias, target in aliases.items() if target == step["skill"])
    return keys


def _walk(wctx, doc, aliases, record_skips):
    """(ready_entries, blocked_by, statuses, satisfied) over the steps in file order."""
    ledger = load_pipeline(wctx["tdir"], wctx["ticket_id"])["steps"]
    memo = {}

    def holds(predicate):
        if predicate not in memo:
            memo[predicate] = bool(PREDICATES[predicate](wctx))
        return memo[predicate]

    ready, blocked, statuses, satisfied = [], None, {}, {}
    for step in doc["steps"]:
        sid = step["id"]
        status = None
        for key in _ledger_keys(step, aliases):
            entry = ledger.get(key)
            if isinstance(entry, dict) and entry.get("status"):
                status = entry.get("status")
                break
        statuses[sid] = status
        when = step.get("when")
        if status == "completed" or (status == SKIPPED_STATUS and (not when or not holds(when))):
            satisfied[sid] = True
            continue
        satisfied[sid] = False
        needs = step.get("needs") or []
        if any(not satisfied.get(need) for need in needs):
            continue
        if when and not holds(when):
            reason = "when: %s is false" % when
            if record_skips and status != SKIPPED_STATUS:
                update_pipeline(wctx["tdir"], wctx["ticket_id"], sid, SKIPPED_STATUS,
                                summary=reason, extra={"reason": reason, "when": when})
            statuses[sid] = SKIPPED_STATUS
            satisfied[sid] = True
            continue
        requires = step.get("requires")
        if requires and not holds(requires):
            if blocked is None:
                blocked = {"step": sid, "predicate": requires, "pointer": _pointer_for(requires, wctx)}
            continue
        ready.append(_entry(wctx, step, status, needs, statuses))
    return ready, blocked, statuses, satisfied


def _entry(wctx, step, status, needs, statuses):
    reason = ("needs satisfied (%s)" % ", ".join("%s %s" % (n, statuses.get(n)) for n in needs)
              if needs else "entry step (no needs)")
    if status in RERUN_STATUSES:
        reason += "; last run recorded %s — ready again" % status
    elif status == SKIPPED_STATUS:
        reason += "; previously skipped, its `when` now holds"
    on_fail = step.get("on_fail")
    if on_fail:
        loops = on_fail.get("max_loops")
        if isinstance(loops, str):
            loops = MAX_LOOPS_NAMES[loops](wctx)
        on_fail = {"relay_to": on_fail["relay_to"], "max_loops": loops}
    args = step.get("args")
    return {
        "step": step["id"],
        "skill": step["skill"],
        "args": args.replace("{ticket_id}", wctx["ticket_id"]) if isinstance(args, str) else None,
        "reason": reason,
        "boundary": step.get("boundary"),
        "on_fail": on_fail,
        "on_replan": step.get("on_replan"),
        "exclusive": bool(step.get("exclusive")),
    }


def _validated(wctx, resolved):
    resolved = resolved or resolve_workflow(wctx.get("checkout_root"))
    doc = validate_workflow_file(resolved["path"])
    return resolved, doc


def next_steps(wctx, resolved=None, record_skips=True):
    """The READY steps for a ticket, per pipeline-state.json.

    A step is satisfied when its ledger status is `completed`, or `skipped`
    while its `when` is still false. A step is READY when every `needs` entry
    is satisfied, it is not itself satisfied, and its `when` holds (a false
    `when` records the step as skipped, with the reason). A needed step in
    any other state -- failed, interrupted, in_progress, handed_off -- is
    simply ready again. `requires` false on a ready step blocks it (reported
    once, as `blocked_by`, with a human pointer). `mode` is `parallel` when
    more than one step is ready, none of them is exclusive and max_parallel
    > 1 (`ready` is then cut to max_parallel entries); otherwise `single` and
    `ready` holds the first ready step. `done` once stop_after completed.
    An epic raises WorkflowError carrying the `{error: "epic", pointer}` payload."""
    ticket = wctx["ticket"]
    if ticket.get("type") == "epic":
        pointer = ("ticket %s is an epic — epics are never shipped directly; run "
                   "/acs:create-design %s first if the epic has no design yet, then "
                   "/acs:create-ticket %s --fan-out to mint its children, then "
                   "/acs:ship <child-id> on each child." % ((wctx["ticket_id"],) * 3))
        raise WorkflowError(pointer, payload={"error": "epic", "ticket": wctx["ticket_id"],
                                              "pointer": pointer})
    resolved, doc = _validated(wctx, resolved)
    aliases = load_phases()["aliases"]
    ready, blocked, statuses, _satisfied = _walk(wctx, doc, aliases, record_skips)
    stop_after = doc.get("stop_after", DEFAULT_STOP_AFTER)
    max_parallel = doc.get("max_parallel", DEFAULT_MAX_PARALLEL)
    done = statuses.get(stop_after) == "completed"
    if done:
        ready = []
    if len(ready) > 1 and max_parallel > 1 and not any(r["exclusive"] for r in ready):
        mode, ready = "parallel", ready[:max_parallel]
    else:
        mode, ready = "single", ready[:1]
    return {
        "ticket": wctx["ticket_id"],
        "mode": mode,
        "ready": ready,
        "done": done,
        "blocked_by": blocked,
        "statuses": statuses,
        "workflow": {"source": resolved["source"], "path": resolved["path"],
                     "name": doc.get("name"), "stop_after": stop_after,
                     "max_parallel": max_parallel},
    }


def pending_needs(wctx, skill, resolved=None):
    """For the FIRST step whose skill is `skill` (or an alias of it): the
    `needs` entries not yet satisfied, as [{step, skill, status}]. Empty when
    the skill is not in the workflow or its needs are all satisfied. Never
    writes the ledger -- the pre-hook advisory reads this."""
    resolved, doc = _validated(wctx, resolved)
    phases = load_phases()
    skill = phases["aliases"].get(skill, skill)
    _ready, _blocked, statuses, satisfied = _walk(wctx, doc, phases["aliases"], False)
    by_id = {step["id"]: step for step in doc["steps"]}
    for step in doc["steps"]:
        if step["skill"] != skill:
            continue
        return [{"step": need, "skill": by_id[need]["skill"], "status": statuses.get(need)}
                for need in step.get("needs") or [] if not satisfied.get(need)]
    return []


# The names the brief uses; the facade re-exports the unambiguous spellings.
resolve = resolve_workflow
validate = validate_workflow
validate_file = validate_workflow_file
next = next_steps  # noqa: A001 -- the brief's name for the walk
