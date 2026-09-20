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
  steps_of / loop_for                 the list and its cycles
  ORDER VALIDATION                    a list with no `needs:` can still be
                                      written in an order that cannot work, so
                                      each step's REQUIRED reads must be
                                      written by an EARLIER step or be a
                                      run-level input. The declarations live
                                      in `skills/<name>/acs.yaml`
                                      (acs_lib.skills), never here: they are
                                      facts about the skill, true in every
                                      workflow, and the same list drives the
                                      runtime input gate — so the validator
                                      and the gate cannot disagree.

That is what makes this not `needs:` by another name. `needs:` was a
per-workflow edge list an author maintained, duplicating what the skills
already knew; this is the skills saying it once and every workflow being
checked against it.

The walk itself is NOT here: with no graph there is no ready-set to compute.
`acs_lib.run` owns the cursor ("the first step not completed"), because that
is a fact about a run rather than about a workflow.

Gates stay INPUT and SAFETY checks; nothing here refuses a skill for running
out of order.
"""

import os

from ._common import GateError, WorkflowError, plugin_root, read_json, write_json  # noqa: F401
from . import schemasubset  # noqa: F401
from . import skills as skills_registry  # noqa: F401
from .schemasubset import (branch_fits_type, deref, equal, is_type,  # noqa: F401
    pointer, schema_errors, type_name)
from .skills import (AGENT_ROLES, OVERRIDE_WORKFLOW_RELPATH, PHASE_GROUPS,  # noqa: F401
    SHIP_FILENAME, SKILLS_DIRNAME, SKILL_SCHEMA_FILENAME, SkillsError,
    WORKFLOWS_DIRNAME, WORKFLOW_SCHEMA_FILENAME, agent_roles_of, agents_dir,
    default_workflow_path, entry_point_of, is_skill, is_step_candidate,
    legs_of, load_manifest, load_manifests, load_schema, manifest_path,
    override_workflow_path, phase_of, reads_of, registered_skills,
    schema_path, skill_agents, skill_dir, skill_legs, skills_dir,
    step_candidates, unreachable_agents, workflows_dir, writes_of)
from . import yamlsubset
from .yamlsubset import YamlSubsetError

#: The only workflow version this build reads.
WORKFLOW_VERSION = 3

#: Artifacts no step writes because the RUN carries them: the subject a run was
#: started from (a ticket, a prompt or a document). A step may require these.
RUN_LEVEL_ARTIFACTS = frozenset({"subject"})

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

def validate_workflow(doc, manifests=None, lines=None, path=None):
    """Schema plus semantic checks; returns `doc`, raises WorkflowError naming
    the source line when `lines` (from yamlsubset.parse) is given.

    Semantic checks, in the order a reader would want them:
      1. every step names a skill that ships and may be a step
      2. every step's REQUIRED reads are written by an earlier step
      3. every loop's endpoints exist and `back_to` precedes `from`
    """
    manifests = manifests if manifests is not None else load_manifests()
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

    errors = schema_errors(load_schema(WORKFLOW_SCHEMA_FILENAME), doc)
    if errors:
        node, message = errors[0]
        _fail("%s: %s" % (pointer(node), message), path, lines, node)

    steps = doc["steps"]
    for index, step in enumerate(steps):
        node = ("steps", index)
        if isinstance(step, dict):
            for key, went in REMOVED_STEP_KEYS.items():
                if key in step:
                    _fail("steps[%d].%s: removed in version 3 — %s"
                          % (index, key, went), path, lines, node)
            _fail("steps[%d]: a step is a skill NAME, not an object" % index, path, lines, node)
        if not is_skill(step):
            _fail("steps[%d]: %r is not a skill that ships (no skills/%s/SKILL.md)"
                  % (index, step, step), path, lines, node)
        entry = (manifests.get(step) or {}).get("leg_of")
        if entry:
            _fail("steps[%d]: %r is a leg of %r, not a step — name %r and let it dispatch"
                  % (index, step, entry, entry), path, lines, node)
        if not is_step_candidate(step, manifests):
            _fail("steps[%d]: %r declares no reads and no writes in skills/%s/acs.yaml, "
                  "so it is a skill rather than a step" % (index, step, step), path, lines, node)

    _validate_order(steps, manifests, path, lines)
    _validate_loops(doc.get("loops") or [], steps, path, lines)
    return doc


def _validate_order(steps, manifests, path, lines):
    """Each step's REQUIRED reads must be written by an EARLIER step, or be a
    run-level artifact. This is the check that replaces `needs:` -- derived
    from what the skills declare, not from an edge list in this file."""
    written = {}
    for index, step in enumerate(steps):
        required, _optional = reads_of(step, manifests)
        for artifact in required:
            if artifact in RUN_LEVEL_ARTIFACTS or artifact in written:
                continue
            producer = _producer_of(artifact, steps, manifests)
            if producer is None:
                _fail("steps[%d]: %s reads %r, which no step in this workflow writes"
                      % (index, step, artifact), path, lines, ("steps", index))
            _fail("steps[%d]: %s reads %r, which no EARLIER step writes — %s writes it "
                  "at step %d" % (index, step, artifact, producer[1], producer[0] + 1),
                  path, lines, ("steps", index))
        for artifact in writes_of(step, manifests):
            written.setdefault(artifact, index)


def _producer_of(artifact, steps, manifests):
    """(index, skill) of the first step that writes `artifact`, else None."""
    for index, step in enumerate(steps):
        if artifact in writes_of(step, manifests):
            return index, step
    return None


def _validate_loops(loops, steps, path, lines):
    order = dict((step, index) for index, step in enumerate(steps))
    for index, loop in enumerate(loops):
        node = ("loops", index)
        for key in ("from", "back_to"):
            if loop[key] not in order:
                _fail("loops[%d].%s: %r is not a step of this workflow"
                      % (index, key, loop[key]), path, lines, node)
        if order[loop["back_to"]] >= order[loop["from"]]:
            _fail("loops[%d]: back_to %r is not EARLIER than from %r — a loop that does "
                  "not go back is not a loop" % (index, loop["back_to"], loop["from"]),
                  path, lines, node)


def validate_workflow_file(path, manifests=None):
    """Parse and validate one file, reporting failures at their line."""
    doc, lines = load_workflow(path)
    return validate_workflow(doc, manifests=manifests, lines=lines, path=path)


def order_warnings(doc, manifests=None):
    """Non-fatal order remarks: an OPTIONAL read placed before its producer.
    Legal and pointless -- create-test-docs reads api-contract when one exists,
    so putting it first means it never will. A warning, never an error.

    A read satisfied by a LOOP is not one of these. `code` reads `verdict`
    when present and `review-code` writes it one step later, but the loop
    sends the run back to `code`, so on iteration 2+ the verdict is exactly
    what `code` is there to act on. Warning about that would train a reader to
    ignore the warnings."""
    manifests = manifests if manifests is not None else load_manifests()
    steps = doc.get("steps") or []
    out = []
    for index, step in enumerate(steps):
        _required, optional = reads_of(step, manifests)
        for artifact in optional:
            producer = _producer_of(artifact, steps, manifests)
            if not producer or producer[0] <= index:
                continue
            if _reachable_by_loop(doc, steps, index, producer[0]):
                continue
            out.append("steps[%d]: %s reads %r when present, but %s does not write it "
                       "until step %d — it will never be present"
                       % (index, step, artifact, producer[1], producer[0] + 1))
    return out


def _reachable_by_loop(doc, steps, reader, producer):
    """True when some loop carries `producer`'s output back round to `reader`:
    the loop's span covers both, so the reader sees it on the next iteration."""
    order = dict((s, i) for i, s in enumerate(steps))
    for loop in loops_of(doc):
        start, end = order.get(loop["back_to"]), order.get(loop["from"])
        if start is None or end is None:
            continue
        if start <= reader <= end and start <= producer <= end:
            return True
    return False


# ---------------------------------------------------------------------------
# Reading a validated workflow
# ---------------------------------------------------------------------------

def steps_of(doc):
    """The step list: skill names, in order."""
    return list(doc.get("steps") or [])


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
