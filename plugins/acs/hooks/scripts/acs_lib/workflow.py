"""acs_lib.workflow — the declarative delivery pipeline.

A workflow is a **list**: `workflows/ship.yaml` (which a consumer may replace
wholesale with `<repo>/.acs/workflows/ship.yaml`) names the skills to run, in
order, plus the loops between them. Version 3 removed everything else — no
`when:`, `paths:`, `requires:`, `needs:`, `id:`, `name:`, `stop_after:`,
`max_parallel`, `exclusive:`, `on_fail:`, `boundary:` or `delivery:` — and the
schema *rejects* those keys rather than ignoring them, so a workflow that
tries to decide for a skill whether it has work fails validation.

This module owns:

  resolve / load_workflow / validate  override-or-default resolution, the
                                      schema (acs_lib.schemasubset, since
                                      hooks may not import jsonschema) and the
                                      semantic checks below
  steps_of / stages_of / loop_for     the list, its parallel groups and its
                                      cycles

A step entry is a skill name, or a LIST of skill names -- a PARALLEL GROUP
whose members `/acs:ship` runs side by side (`- [docs-sync, create-e2e-tests]`).
Each entry is a STAGE; the stages run in order, and a group's members may all
be in progress at once. A group is written by the author, never derived: the
skills declare nothing about each other, so nothing could derive it.

A workflow is an ORCHESTRATOR, not a contract. It keeps the order the skills
run in and nothing else: each skill is independent, reads what it finds, and
falls back to the run's subject when an upstream artifact is absent. So the
validator checks only what a list can get wrong on its own -- a name that is
not a skill, a leg named in place of its entry point, a loop that does not go
back -- and never what a skill needs. A skill that would be strict about its
inputs could not be run on its own.

The walk itself is NOT here: with no graph there is no ready-set to compute.
`acs_lib.run` owns the cursor ("the first step not completed"), because that
is a fact about a run rather than about a workflow.

Gates stay SAFETY checks; nothing here refuses a skill for running out of
order.
"""

import os

from ._common import GateError, WorkflowError, plugin_root, read_json, write_json  # noqa: F401
from . import schemasubset  # noqa: F401
from . import skills as skills_registry  # noqa: F401
from .schemasubset import (branch_fits_type, deref, equal, is_type,  # noqa: F401
    pointer, schema_errors, type_name)
from .skills import (OVERRIDE_WORKFLOW_RELPATH, SHIP_FILENAME,  # noqa: F401
    WORKFLOW_SCHEMA_FILENAME, default_workflow_path, entry_point_of, is_skill,
    load_schema, override_workflow_path, workflows_dir)
from . import yamlsubset
from .yamlsubset import YamlSubsetError

#: The only workflow version this build reads.
WORKFLOW_VERSION = 3

#: The v2 keys version 3 removed. Named so the error can say where each went
#: rather than only that it is unknown.
REMOVED_KEYS = {
    "name": "the file name is the workflow's name",
    "stop_after": "the list ends where the run ends",
    "max_parallel": "steps run in the order they are written",
    "delivery": "the plan records the delivery path; /acs:code dispatches on it",
}
REMOVED_STEP_KEYS = {
    "id": "a step is a skill; state is keyed by the skill name",
    "skill": "a step IS the skill name, not an object with a `skill` key",
    "needs": "the written order is the dependency order",
    "when": "the skill decides for itself and records why",
    "paths": "the skill decides for itself and records why",
    "requires": "the skill's own start check",
    "exclusive": "steps run one at a time",
    "on_fail": "the `loops:` entry",
    "boundary": "removed with the per-path machinery",
}


# ---------------------------------------------------------------------------
# Loading
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


def workflow_name(path):
    """The workflow's name: its file name without the extension. There is no
    `name:` key -- the file IS the name, and run.json records it as such."""
    return os.path.splitext(os.path.basename(path))[0]


def _fail(reason, path, lines, node):
    raise WorkflowError(reason, path=path, line=yamlsubset.line_for(lines or {}, node))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_workflow(doc, lines=None, path=None):
    """Schema plus semantic checks; returns `doc`, raises WorkflowError naming
    the source line when `lines` (from yamlsubset.parse) is given.

    Semantic checks, in the order a reader would want them:
      1. every step names a skill that ships and is not another skill's leg
      2. every loop's endpoints exist and `back_to` precedes `from`
    """
    if not isinstance(doc, dict):
        _fail("(document): expected object, got %s" % type_name(doc), path, lines, ())

    for key, went in REMOVED_KEYS.items():
        if key in doc:
            _fail("%s: removed in version 3 — %s" % (key, went), path, lines, (key,))

    if doc.get("version") != WORKFLOW_VERSION:
        _fail("version: %r is not supported — this build reads version %d. A version-2 "
              "file carries conditions and constraints (`when`, `needs`, `paths`, "
              "`delivery`) that version 3 removed; rewrite it as a list of skill names."
              % (doc.get("version"), WORKFLOW_VERSION), path, lines, ("version",))

    # The step SHAPE is checked before the schema, so an author who wrote a
    # version-2 step gets "needs: removed in version 3 — the written order is
    # the dependency order" rather than "expected string, got object". Naming
    # where a key went is the whole reason REMOVED_STEP_KEYS exists.
    for index, step in enumerate(doc.get("steps") or []):
        if not isinstance(step, dict):
            continue
        node = ("steps", index)
        # Every removed key this step carries, in one message: a real
        # version-2 step carries `id` AND `needs` AND often `when`, and an
        # author who has to fix them one round trip at a time is being told
        # off three times for one mistake.
        gone = [(key, REMOVED_STEP_KEYS[key]) for key in REMOVED_STEP_KEYS if key in step]
        if gone:
            _fail("steps[%d]: removed in version 3 — %s. A step is a skill NAME, not an "
                  "object." % (index, "; ".join("%s (%s)" % (k, w) for k, w in gone)),
                  path, lines, node)
        _fail("steps[%d]: a step is a skill NAME, not an object" % index, path, lines, node)

    errors = schema_errors(load_schema(WORKFLOW_SCHEMA_FILENAME), doc)
    if errors:
        node, message = errors[0]
        _fail("%s: %s" % (pointer(node), message), path, lines, node)

    seen = set()
    for index, entry in enumerate(doc["steps"]):
        members = entry if isinstance(entry, list) else [entry]
        for position, step in enumerate(members):
            node = ("steps", index, position) if isinstance(entry, list) else ("steps", index)
            label = ("steps[%d][%d]" % (index, position) if isinstance(entry, list)
                     else "steps[%d]" % index)
            if not is_skill(step):
                _fail("%s: %r is not a skill that ships (no skills/%s/SKILL.md)"
                      % (label, step, step), path, lines, node)
            leg_entry = entry_point_of(step)
            if leg_entry:
                _fail("%s: %r is a leg of %r, not a step — name %r and let it dispatch"
                      % (label, step, leg_entry, leg_entry), path, lines, node)
            if step in seen:
                _fail("%s: %r appears twice — a skill is one step of a run"
                      % (label, step), path, lines, node)
            seen.add(step)

    _validate_loops(doc.get("loops") or [], doc["steps"], path, lines)
    return doc


def _validate_loops(loops, entries, path, lines):
    """Loop endpoints are whole stages: a loop that started or ended inside a
    parallel group would re-enter half of it, and what the other half had
    already done would be neither kept nor redone."""
    order = {}
    grouped = set()
    for index, entry in enumerate(entries):
        for step in (entry if isinstance(entry, list) else [entry]):
            order[step] = index
            if isinstance(entry, list):
                grouped.add(step)
    for index, loop in enumerate(loops):
        node = ("loops", index)
        for key in ("from", "back_to"):
            if loop[key] not in order:
                _fail("loops[%d].%s: %r is not a step of this workflow"
                      % (index, key, loop[key]), path, lines, node)
            if loop[key] in grouped:
                _fail("loops[%d].%s: %r is inside a parallel group; a loop's ends "
                      "must be steps of their own" % (index, key, loop[key]),
                      path, lines, node)
        if order[loop["back_to"]] >= order[loop["from"]]:
            _fail("loops[%d]: back_to %r is not EARLIER than from %r — a loop that does "
                  "not go back is not a loop" % (index, loop["back_to"], loop["from"]),
                  path, lines, node)


def validate_workflow_file(path):
    """Parse and validate one file, reporting failures at their line."""
    doc, lines = load_workflow(path)
    return validate_workflow(doc, lines=lines, path=path)


# ---------------------------------------------------------------------------
# Reading a validated workflow
# ---------------------------------------------------------------------------

def stages_of(doc):
    """The stages, in order: each a list of the skill names that may run at
    once -- one name for a plain step, several for a parallel group."""
    return [list(entry) if isinstance(entry, list) else [entry]
            for entry in (doc.get("steps") or [])]


def steps_of(doc):
    """Every step, flattened, in order: skill names. A group's members keep
    their written order, which is the order `/acs:ship` starts them in."""
    return [step for stage in stages_of(doc) for step in stage]


def stage_of(doc, step):
    """The stage (list of names) that holds `step`, else None."""
    for stage in stages_of(doc):
        if step in stage:
            return stage
    return None


def stage_index(doc, step):
    """The index of the stage that holds `step`, else None."""
    for index, stage in enumerate(stages_of(doc)):
        if step in stage:
            return index
    return None


def loops_of(doc):
    return list(doc.get("loops") or [])


def loop_for(doc, step):
    """The loop whose `from` is `step`, else None."""
    for loop in loops_of(doc):
        if loop["from"] == step:
            return loop
    return None


def has_step(doc, step):
    return step in steps_of(doc)


def step_index(doc, step):
    steps = steps_of(doc)
    return steps.index(step) if step in steps else None
