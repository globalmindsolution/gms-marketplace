"""acs_lib.analysis_loop — the /acs:analyze-requirements controller (ADR-0114).

The skill's loop used to be prose: SKILL.md told the coordinator which pass ran
next, when the cap was spent, how the judges' findings joined into a pass, and
the coordinator decided each of those itself. This module owns those decisions
instead. It never dispatches an agent; it answers ONE question -- what is the
next action? -- and records what an action produced by reading the artifacts
itself:

    plan -> survey -> [synthesize] -> clarify -> draft -> review
                                                   ^         |
                                                   +-- n+1 --+-> publish -> completed

plus `blocked` (a defect in the machinery, or a question only the user can
settle: no iteration is spent) and `failed` (the review stalled, or the cap of
3 draft -> review cycles is spent).

**Derived, never asserted.** No `record-*` verb takes a verdict from its caller.
`record_review` parses every judge slice's `<result>` snapshot (the one the
SubagentStop hook writes, or the coordinator on a host that does not fire it)
and derives the pass from the findings in it.

State lives in `steps/analyze-requirements/loop.json`, written only here and
held to `schemas/analysis-loop.schema.json` on every write. Publication -- the
deterministic checks, the byte-for-byte copy, the docs-folder-only commit --
is `acs_lib.analysis_publish`.
"""

import hashlib
import os
import xml.etree.ElementTree as ET

from ._common import GateError, now_iso, read_json, write_json, write_text
from .lifecycle import _SLICE_RE, extract_message, open_clarifications, \
    phase_artifact_path, validate_message
from .notes import merge_files
from .run import iteration_dir, step_dir
from .schemasubset import schema_errors
from .skills import load_schema
from .step import load_state

SKILL = "analyze-requirements"
#: The draft -> review cycles a run may spend. Fixed: this skill has no
#: path-driven verify depth.
CAP = 3
LOOP_FILENAME = "loop.json"
SCHEMA_FILENAME = "analysis-loop.schema.json"
DRAFT_FILENAME = "analysis.md"

ANALYST = "analyst"
IMPACT_ANALYST = "impact-analyst"
REVIEWER = "impact-reviewer"

#: The analyst's own survey lane, and the slice id of its synthesis pass.
REQUIREMENTS_SLICE = "requirements"
SYNTHESIS_SLICE = "synthesis"
#: The one impact lane's slice when the coordinator declares no areas.
WHOLE_REPO_SLICE = "repo"
#: Slice ids a code area may not take: it is sliced as `area-<name>` instead,
#: so an area literally named `requirements` cannot overwrite the analyst's lane.
RESERVED_SLICES = frozenset({REQUIREMENTS_SLICE, SYNTHESIS_SLICE, WHOLE_REPO_SLICE, "survey"})

#: The impact reviewer's three judge slices, in join order, with the check
#: dimensions each owns (number, name).
JUDGE_SLICES = (
    ("surface", ((2, "completeness"), (3, "api-surface"))),
    ("form", ((4, "front-matter"), (5, "structure"), (6, "scope"))),
    ("evidence", ((1, "grounding"), (7, "authoring-conformance"))),
)

#: Loop phases. A phase is the action `next` hands out while nothing blocks.
PHASES = ("survey", "synthesize", "clarify", "draft", "review", "publish",
          "completed", "failed")
TERMINAL_PHASES = ("completed", "failed")
#: Every action `next` can print.
ACTIONS = ("plan",) + PHASES[:-2] + ("completed", "blocked", "failed")
#: The record verb each phase is reported with.
RECORD_VERBS = {
    "survey": "record-survey", "synthesize": "record-synthesis",
    "clarify": "record-clarify", "draft": "record-draft",
    "review": "record-review", "publish": "record-publication",
}
BLOCK_KINDS = ("machinery", "needs_input", "agent_failed")
STOP_REASONS = ("stalled", "cap")
RESULT_STATUSES = ("completed", "failed", "needs_input")

_CLI = 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" analysis '


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def loop_path(rdir):
    return os.path.join(step_dir(rdir, SKILL), LOOP_FILENAME)


def draft_path(rdir):
    """The working draft: one per run, revised in place, never renumbered."""
    return os.path.join(step_dir(rdir, SKILL), DRAFT_FILENAME)


def iter_path(rdir, iteration, name):
    return os.path.join(iteration_dir(rdir, SKILL, iteration), name)


def snapshot_path(rdir, iteration, phase, slice_id=None):
    """Where SubagentStop persists a phase's `<result>` -- the same function
    the hook itself uses, so the two can never name different files."""
    return phase_artifact_path(rdir, SKILL, iteration, phase, slice_id)


def notes_path(rdir, slice_id=None):
    """Iteration 1's survey notes: a lane's own file, or the joined one."""
    name = "authoring-%s.md" % slice_id if slice_id else "authoring.md"
    return iter_path(rdir, 1, name)


def lane_report_path(rdir, lane):
    return iter_path(rdir, 1, "%s-%s.json" % (lane["phase"], lane["slice"]))


def review_report_path(rdir, iteration, slice_id=None):
    name = "%s-%s.md" % (REVIEWER, slice_id) if slice_id else "%s.md" % REVIEWER
    return iter_path(rdir, iteration, name)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def load_loop(rdir):
    doc = read_json(loop_path(rdir))
    return doc if isinstance(doc, dict) else None


def save_loop(rdir, loop):
    """The only writer of loop.json. Validated first: a controller that wrote
    a document its own schema refuses would be asserting state, not deriving it."""
    loop["updated_at"] = now_iso()
    errors = schema_errors(load_schema(SCHEMA_FILENAME), loop)
    if errors:
        raise GateError("refusing to write an invalid loop.json: %s" % "; ".join(
            "%s: %s" % (path or "/", msg) for path, msg in errors[:5]))
    write_json(loop_path(rdir), loop)
    return loop


def invocations(rdir):
    """This step's invocations in this run, oldest first."""
    return list(load_state(rdir, SKILL).get("invocations") or [])


def area_slices(areas):
    """[{area, slice}] for the declared code areas, in order, de-duplicated.
    No areas -> one impact lane over the whole repository."""
    out, seen = [], set()
    for raw in areas or ():
        area = (raw or "").strip().strip("/")
        if not area or area in seen:
            continue
        seen.add(area)
        sid = "area-%s" % area if area in RESERVED_SLICES else area
        if not _SLICE_RE.match(sid):
            raise GateError("area %r cannot name a slice: use the area's directory basename "
                            "(letters, digits, '_' or '-', at most 40 characters)" % raw)
        out.append({"area": area, "slice": sid})
    if not out:
        out.append({"area": None, "slice": WHOLE_REPO_SLICE})
    return out


def new_loop(run_id, ticket_id, areas, invocation):
    lanes = [{"lane": "requirements", "phase": ANALYST, "slice": REQUIREMENTS_SLICE,
              "area": None}]
    lanes += [{"lane": "impact", "phase": IMPACT_ANALYST, "slice": a["slice"],
               "area": a["area"]} for a in area_slices(areas)]
    now = now_iso()
    return {
        "version": 1, "skill": SKILL, "run_id": run_id, "ticket_id": ticket_id,
        "invocation": invocation, "cap": CAP, "iteration": 1, "phase": "survey",
        "lanes": lanes, "blocked": None, "stop_reason": None, "failure": None,
        "history": [], "draft": None, "publication": None, "needs_input": None,
        "events": [{"at": now, "event": "plan",
                    "detail": "lanes: %s" % ", ".join(l["slice"] for l in lanes)}],
        "created_at": now, "updated_at": now,
    }


def plan(rdir, run_id, ticket_id, areas):
    """Declare the survey lanes once. Refused while a loop of this invocation
    is still live: the areas are decided before the survey, never mid-loop."""
    loop = load_loop(rdir)
    opened = invocations(rdir)
    if loop is not None and not _stale(loop, opened):
        raise GateError("the analysis loop is already planned (next action: %s); run "
                        "`acs.py analysis next`" % current_action(loop))
    return save_loop(rdir, new_loop(run_id, ticket_id, areas, len(opened)))


def _stale(loop, opened):
    """A finished loop is history once the step invocation it ran under was
    itself finished (Finish ran: `completed` or `failed`) and a later one has
    opened -- that later invocation plans afresh. A loop that ended but whose
    invocation was interrupted before Finish is NOT stale: the resume goes
    straight to Finish rather than re-running the analysis."""
    if loop.get("phase") not in TERMINAL_PHASES:
        return False
    planned = int(loop.get("invocation") or 0)
    if len(opened) <= planned or planned < 1:
        return len(opened) > planned
    entry = opened[planned - 1] or {}
    return (entry.get("status") in ("completed", "failed")
            or (entry.get("status") == "interrupted"
                and entry.get("stop_reason") == "needs_input"))


def _event(loop, event, detail=""):
    loop.setdefault("events", []).append({"at": now_iso(), "event": event, "detail": detail})


def current_action(loop):
    if loop.get("phase") in TERMINAL_PHASES:
        return loop["phase"]
    return "blocked" if loop.get("blocked") else loop["phase"]


# ---------------------------------------------------------------------------
# The next action (read-only)
# ---------------------------------------------------------------------------

def next_action(rdir, loop, opened=None):
    """The ONE action the coordinator performs next, as a JSON-ready dict.
    Reads nothing but the loop (and the step's invocations, `opened`) and
    writes nothing at all."""
    if loop is None or (opened is not None and _stale(loop, opened)):
        return {"action": "plan", "iteration": 0, "loop": loop_path(rdir),
                "command": _CLI + "plan --areas <area>,<area>",
                "note": "declare the code areas once (empty for one impact lane over "
                        "the whole repository)"}
    phase, n = loop["phase"], loop["iteration"]
    if phase == "failed":
        failure = loop.get("failure") or {}
        return {"action": "failed", "iteration": n, "loop": loop_path(rdir),
                "stop_reason": loop.get("stop_reason"), "reason": failure.get("reason"),
                "findings": _last_blocking(loop)}
    if phase == "completed":
        out = {"action": "completed", "iteration": n, "loop": loop_path(rdir),
               "publication": loop.get("publication"),
               "iterations": [{"iteration": h["iteration"], "passed": h["passed"],
                               "blocking": len(h["blocking"])} for h in loop["history"]]}
        if loop.get("needs_input"):
            # The not-ready arm: the analysis is published (ready_for_planning
            # false) and the run still stops for the user's answer.
            out.update(action="blocked", kind="needs_input", retry=None,
                       reason=loop["needs_input"]["reason"])
        return out
    action = _render(rdir, loop, phase, n)
    blocked = loop.get("blocked")
    if blocked:
        return {"action": "blocked", "iteration": n, "loop": loop_path(rdir),
                "kind": blocked["kind"], "reason": blocked["reason"],
                "retry": blocked["retry"], "retry_action": action}
    return action


def _render(rdir, loop, phase, n):
    out = {"action": phase, "iteration": n, "loop": loop_path(rdir),
           "record": _CLI + RECORD_VERBS[phase]}
    if phase == "survey":
        out["lanes"] = [_lane_action(rdir, lane) for lane in loop["lanes"]]
        out["joined_notes"] = notes_path(rdir)
    elif phase == "synthesize":
        out.update(_agent(ANALYST), slice=SYNTHESIS_SLICE, **{"pass": "synthesis"})
        out.update(inputs=[notes_path(rdir)], notes=notes_path(rdir, SYNTHESIS_SLICE),
                   report=iter_path(rdir, 1, "%s-%s.json" % (ANALYST, SYNTHESIS_SLICE)),
                   snapshot=snapshot_path(rdir, 1, ANALYST, SYNTHESIS_SLICE),
                   joined_notes=notes_path(rdir))
        out["record"] = _CLI + "record-synthesis"
    elif phase == "clarify":
        out.update(notes=notes_path(rdir),
                   record=_CLI + "record-clarify [--blocking-open]")
        out["then"] = "draft"
    elif phase == "draft":
        out.update(_agent(ANALYST), slice=None, **{"pass": "draft"})
        notes = [notes_path(rdir)]
        if n >= 2:
            notes.append(iter_path(rdir, n, "authoring.md"))
        out.update(draft=draft_path(rdir), notes=notes,
                   report=iter_path(rdir, n, "%s.json" % ANALYST),
                   snapshot=snapshot_path(rdir, n, ANALYST),
                   findings=_last_blocking(loop) if n >= 2 else [],
                   not_ready=(loop.get("needs_input") or {}).get("reason"))
    elif phase == "review":
        out.update(_agent(REVIEWER))
        out["slices"] = [{"slice": sid,
                          "dimensions": [{"number": num, "name": name} for num, name in dims],
                          "report": review_report_path(rdir, n, sid),
                          "snapshot": snapshot_path(rdir, n, REVIEWER, sid)}
                         for sid, dims in JUDGE_SLICES]
        out.update(joined_report=review_report_path(rdir, n), draft=draft_path(rdir),
                   analyst_report=iter_path(rdir, n, "%s.json" % ANALYST),
                   notes=[notes_path(rdir)] + ([iter_path(rdir, n, "authoring.md")]
                                               if n >= 2 else []))
    elif phase == "publish":
        out.update(draft=draft_path(rdir), published=bool(loop.get("publication")),
                   commands=[_CLI + "publish", _CLI + "record-publication"])
    return out


def _agent(phase):
    return {"agent": "acs:%s-%s" % (SKILL, phase), "phase": phase}


def _lane_action(rdir, lane):
    out = dict(_agent(lane["phase"]), lane=lane["lane"], slice=lane["slice"],
               area=lane.get("area"), notes=notes_path(rdir, lane["slice"]),
               report=lane_report_path(rdir, lane),
               snapshot=snapshot_path(rdir, 1, lane["phase"], lane["slice"]))
    if lane["phase"] == ANALYST:
        out["pass"] = "requirements"
    return out


def _last_blocking(loop):
    history = loop.get("history") or []
    return list(history[-1]["blocking"]) if history else []


# ---------------------------------------------------------------------------
# Reading what an action produced
# ---------------------------------------------------------------------------

def read_result(path, phase, iteration, slice_id, ticket_id):
    """(element, None) for a usable `<result>` snapshot, else (None, reason).

    Usable means: the file exists, holds a well-formed `<result>`, and its
    skill / phase / iteration / slice (and ticket-id, when given) are the ones
    this action dispatched. A snapshot for the wrong slice is a defect in the
    machinery, never a result to count."""
    if not os.path.isfile(path):
        return None, ("missing <result> snapshot %s (the SubagentStop hook writes it; on a "
                      "host that does not fire the hook, write the <task> and <result> there "
                      "yourself)" % path)
    with open(path, encoding="utf-8") as handle:
        message = extract_message(handle.read())
    if message is None:
        return None, "no <result> element in %s" % path
    errors = validate_message(message)
    if errors:
        return None, "malformed <result> in %s: %s" % (path, "; ".join(errors))
    root = ET.fromstring(message)
    if root.tag != "result":
        return None, "%s holds a <%s>, not a phase <result>" % (path, root.tag)
    expected = {"skill": SKILL, "phase": phase, "iteration": str(iteration),
                "slice": slice_id}
    for attr, want in expected.items():
        got = root.get(attr)
        if got != want:
            return None, "%s: %s=%r, expected %r" % (path, attr, got, want)
    got_ticket = root.get("ticket-id")
    if got_ticket is not None and ticket_id and got_ticket != ticket_id:
        return None, "%s: ticket-id=%r, expected %r" % (path, got_ticket, ticket_id)
    if root.get("status") not in RESULT_STATUSES:
        return None, "%s: status=%r, expected one of %s" % (
            path, root.get("status"), ", ".join(RESULT_STATUSES))
    return root, None


def _children_text(root, tag):
    return "; ".join(" ".join("".join(el.itertext()).split())
                     for el in root.iter(tag) if "".join(el.itertext()).strip())


def _status_block(loop, root, who, needs_input_phase=None):
    """Block on a result that did not complete. True when it blocked."""
    status = root.get("status")
    if status == "completed":
        return False
    if status == "needs_input":
        detail = _children_text(root, "question") or _children_text(root, "questions")
        _block(loop, "needs_input", "%s returned needs_input%s" % (
            who, ": %s" % detail if detail else ""), phase=needs_input_phase)
    else:
        detail = _children_text(root, "error") or _children_text(root, "stop-reason")
        _block(loop, "agent_failed", "%s returned status=failed%s" % (
            who, ": %s" % detail if detail else ""))
    return True


def _require_files(loop, paths, json_paths=()):
    """Block on the first missing artifact (or unreadable JSON report)."""
    for path in paths:
        if not os.path.isfile(path):
            _block(loop, "machinery", "missing artifact %s" % path)
            return False
    for path in json_paths:
        if not isinstance(read_json(path), dict):
            _block(loop, "machinery", "report %s is not a JSON object" % path)
            return False
    return True


def _block(loop, kind, reason, phase=None):
    """Stop the loop on a defect or a question. The phase stays (or, for a
    question raised mid-draft, moves to `clarify`); no iteration is spent."""
    if phase:
        loop["phase"] = phase
    loop["blocked"] = {"kind": kind, "reason": reason, "retry": loop["phase"],
                       "at": now_iso()}
    _event(loop, "blocked", reason)


def _advance(loop, phase, event, detail=""):
    loop["blocked"] = None
    loop["phase"] = phase
    _event(loop, event, detail)


def _expect(loop, phase):
    if loop is None:
        raise GateError("no analysis loop for this run: run `acs.py analysis next`, then "
                        "`acs.py analysis plan`")
    if loop["phase"] in TERMINAL_PHASES:
        raise GateError("the analysis loop has already %s" % loop["phase"])
    if loop["phase"] != phase:
        raise GateError("out of order: the loop's next action is %r, not %r"
                        % (current_action(loop), phase))


def sha256_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


# ---------------------------------------------------------------------------
# record-* verbs
# ---------------------------------------------------------------------------

def record_survey(rdir, loop):
    _expect(loop, "survey")
    for lane in loop["lanes"]:
        root, err = read_result(snapshot_path(rdir, 1, lane["phase"], lane["slice"]),
                                lane["phase"], 1, lane["slice"], loop["ticket_id"])
        if err:
            _block(loop, "machinery", err)
            return loop
        who = "%s lane %r" % (lane["phase"], lane["slice"])
        if _status_block(loop, root, who):
            return loop
        report = lane_report_path(rdir, lane)
        if not _require_files(loop, [notes_path(rdir, lane["slice"]), report], [report]):
            return loop
    merge_files([notes_path(rdir, lane["slice"]) for lane in loop["lanes"]], notes_path(rdir))
    nxt = "synthesize" if len(loop["lanes"]) > 1 else "clarify"
    _advance(loop, nxt, "survey", "%d lane(s) joined into %s" % (len(loop["lanes"]),
                                                                 notes_path(rdir)))
    return loop


def record_synthesis(rdir, loop):
    _expect(loop, "synthesize")
    root, err = read_result(snapshot_path(rdir, 1, ANALYST, SYNTHESIS_SLICE), ANALYST, 1,
                            SYNTHESIS_SLICE, loop["ticket_id"])
    if err:
        _block(loop, "machinery", err)
        return loop
    if _status_block(loop, root, "the synthesis pass"):
        return loop
    report = iter_path(rdir, 1, "%s-%s.json" % (ANALYST, SYNTHESIS_SLICE))
    if not _require_files(loop, [notes_path(rdir, SYNTHESIS_SLICE), report], [report]):
        return loop
    merge_files([notes_path(rdir, lane["slice"]) for lane in loop["lanes"]]
                + [notes_path(rdir, SYNTHESIS_SLICE)], notes_path(rdir))
    _advance(loop, "clarify", "synthesis", "synthesis joined last into %s" % notes_path(rdir))
    return loop


def record_clarify(rdir, loop, tdir, blocking_open=False):
    """The coordinator asked the user (or found nothing to ask). The one thing
    only it can know -- whether a question it could not settle BLOCKS -- is
    the flag; the ledger's open count is read here, not reported."""
    _expect(loop, "clarify")
    if not _require_files(loop, [notes_path(rdir)]):
        return loop
    open_count = len(open_clarifications(tdir)) if tdir else 0
    loop["needs_input"] = None
    if blocking_open:
        # references/not-ready-for-planning.md: the analysis is still drafted,
        # reviewed and published (ready_for_planning: false) -- it is what the
        # answers come back to -- and the loop then ends `blocked` needs_input
        # rather than `completed`. No iteration is spent on the question.
        loop["needs_input"] = {
            "reason": "a blocking question is still open after the follow-up round (%d open "
                      "in the ledger): draft with ready_for_planning false, publish, then "
                      "finish as needs_input per references/not-ready-for-planning.md"
                      % open_count}
    _advance(loop, "draft", "clarify", "%d question(s) open in the ledger%s" % (
        open_count, "; a blocking one stays open" if blocking_open else ""))
    return loop


def record_draft(rdir, loop):
    _expect(loop, "draft")
    n = loop["iteration"]
    root, err = read_result(snapshot_path(rdir, n, ANALYST), ANALYST, n, None,
                            loop["ticket_id"])
    if err:
        _block(loop, "machinery", err)
        return loop
    if _status_block(loop, root, "the draft pass", needs_input_phase="clarify"):
        return loop
    report = iter_path(rdir, n, "%s.json" % ANALYST)
    needed = [draft_path(rdir), report]
    if n >= 2:
        needed.append(iter_path(rdir, n, "authoring.md"))
    if not _require_files(loop, needed, [report]):
        return loop
    loop["draft"] = {"iteration": n, "sha256": sha256_file(draft_path(rdir))}
    _advance(loop, "review", "draft", "iteration %d draft %s" % (n, loop["draft"]["sha256"][:12]))
    return loop


def parse_findings(root, slice_id):
    out = []
    for el in root.iter("finding"):
        out.append({"slice": slice_id, "severity": (el.get("severity") or "").strip(),
                    "dimension": (el.get("dimension") or "").strip(),
                    "file": (el.get("file") or "").strip(),
                    "text": "".join(el.itertext()).strip()})
    return out


def finding_key(finding):
    """What makes two blocking findings the same: dimension, file and the text
    with its whitespace normalised. The slice and the severity wording are not."""
    return (finding["dimension"], finding["file"], " ".join(finding["text"].split()))


def dedupe(findings):
    """(kept, dropped): the first of each key kept verbatim, in order."""
    kept, dropped, seen = [], [], {}
    for finding in findings:
        key = finding_key(finding)
        if key in seen:
            dropped.append({"finding": finding, "duplicate_of": seen[key]})
            continue
        seen[key] = finding
        kept.append(finding)
    return kept, dropped


def blocking_set(entry):
    return sorted(set(finding_key(f) for f in entry["blocking"]))


def record_review(rdir, loop):
    _expect(loop, "review")
    n = loop["iteration"]
    slices, blocking = [], []
    for sid, _dims in JUDGE_SLICES:
        root, err = read_result(snapshot_path(rdir, n, REVIEWER, sid), REVIEWER, n, sid,
                                loop["ticket_id"])
        if err:
            _block(loop, "machinery", err)
            return loop
        if root.get("status") == "needs_input":
            _status_block(loop, root, "judge slice %r" % sid)
            return loop
        if not _require_files(loop, [review_report_path(rdir, n, sid)]):
            return loop
        findings = parse_findings(root, sid)
        status = root.get("status")
        slices.append({"slice": sid, "status": status, "findings": len(findings),
                       "blocking": sum(1 for f in findings if f["severity"] == "blocking")})
        blocking += [f for f in findings if f["severity"] == "blocking"]
        if status != "completed":
            # A slice that could not review fails the iteration -- never "pass
            # with a missing slice" -- and its errors are what the next draft fixes.
            blocking.append({"slice": sid, "severity": "blocking", "dimension": "review-failed",
                             "file": sid, "text": _children_text(root, "error")
                             or "judge slice %s returned status=failed" % sid})
    kept, dropped = dedupe(blocking)
    joined = review_report_path(rdir, n)
    merge_files([review_report_path(rdir, n, sid) for sid, _d in JUDGE_SLICES], joined)
    _append_dedupe_section(joined, dropped)
    passed = all(s["status"] == "completed" for s in slices) and not kept
    entry = {"iteration": n, "passed": passed, "blocking": kept,
             "dropped": len(dropped), "slices": slices,
             "draft_sha256": sha256_file(draft_path(rdir)) if os.path.isfile(draft_path(rdir))
             else None, "at": now_iso()}
    loop["history"].append(entry)
    if passed:
        _advance(loop, "publish", "review", "iteration %d passed" % n)
        return loop
    return _after_failed_iteration(loop, entry)


def _after_failed_iteration(loop, entry):
    """Stalled, capped, or the next draft: the transition a failed iteration
    takes, whether the judges or publish's checks failed it."""
    n = entry["iteration"]
    previous = [h for h in loop["history"] if h["iteration"] == n - 1]
    if previous and blocking_set(previous[-1]) == blocking_set(entry):
        return _fail(loop, "stalled", "iteration %d returned the same %d blocking finding(s) as "
                     "iteration %d; another draft pass would learn nothing"
                     % (n, len(entry["blocking"]), n - 1))
    if n >= loop["cap"]:
        return _fail(loop, "cap", "%d blocking finding(s) remain after iteration %d of %d"
                     % (len(entry["blocking"]), n, loop["cap"]))
    loop["iteration"] = n + 1
    _advance(loop, "draft", "review", "iteration %d failed with %d blocking finding(s)"
             % (n, len(entry["blocking"])))
    return loop


def _fail(loop, stop_reason, reason):
    loop["blocked"] = None
    loop["phase"] = "failed"
    loop["stop_reason"] = stop_reason
    loop["failure"] = {"stop_reason": stop_reason, "reason": reason,
                       "iteration": loop["iteration"]}
    _event(loop, "failed", reason)
    return loop


def _append_dedupe_section(path, dropped):
    with open(path, encoding="utf-8") as handle:
        text = handle.read().rstrip("\n")
    lines = ["", "", "## De-duplicated findings", ""]
    if not dropped:
        lines.append("_None._")
    for item in dropped:
        f, orig = item["finding"], item["duplicate_of"]
        lines.append("- %s / %s / %s — duplicate of %s's finding" % (
            f["slice"], f["dimension"], f["file"], orig["slice"]))
    write_text(path, text + "\n".join(lines) + "\n")


def record_check_failure(loop, findings):
    """Publish's deterministic checks failed on the reviewed draft: the
    iteration did not pass after all, and its findings go to the next draft."""
    entry = loop["history"][-1]
    entry["passed"] = False
    entry["blocking"] = dedupe(entry["blocking"] + findings)[0]
    loop["blocked"] = None
    return _after_failed_iteration(loop, entry)

