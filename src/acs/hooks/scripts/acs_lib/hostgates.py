"""acs_lib.hostgates — does this runtime actually fire acs's hooks?

acs's enforcement is carried entirely by the hooks `hooks/hooks.json` binds to
Claude Code lifecycle events. On a host that does not raise those events none of
it runs: a skill can start with an unmet predecessor, an executor can write
outside its file map, and no phase artifact is validated. The skills still read
as instructions, so a pipeline appears to execute and nothing says otherwise.

This module makes that state answerable at runtime, from evidence rather than
inference. `run_pre_payload` records a DEDICATED gate-evidence artifact as one
of its first actions, before the gate itself passes or blocks, and the only
other caller passes `record_marker=False` precisely so `acs.py gate` cannot
forge one. The artifact is therefore written by the PreToolUse(Skill) hook and
by nothing else: if it is there, the kernel ran the gate.

The artifact is its own file, not a field on the session marker. That marker
carries cost attribution, whose invariants run opposite to these: attribution
must never be clobbered by an envelope that cannot supply it and must age out
honestly, while gate evidence must be rewritten by every fire and spent once.
Sharing one file cost three defects before this was separated -- a consumed
stamp surviving a genuine fire, a correlation pair split across two sessions,
and an expired correlation revived by a refreshed timestamp. This artifact
holds no `session_id`, `transcript_path` or `cwd`, so it cannot corrupt
attribution: it has none.

The converse does not hold, and nothing here claims it. That write is fail-open
by design (MAR-514: a marker-write bug must never block a gated skill), so a
failure to record is indistinguishable from a runtime that never fired the hook.
Absence of the evidence is therefore reported as absence of the evidence --
never as proof that the gate did not fire -- in the reason, in the verdict's
field names and in the notice's wording alike.

Three conditions make the evidence answer for THIS invocation rather than some
earlier one: it is fresh and belongs to this checkout, it was recorded for this
entry-point skill, and it has not already been spent by another run
(`consume_gate_evidence`). Anything else is reported ungated with the reason
that says which condition failed -- never silently.
"""

import os
from datetime import datetime, timezone

from ._common import now_iso, parse_iso, read_json, write_json
from .repo import sessions_dir, session_marker_path

#: settings.hook_gates.when_absent. `warn` never blocks a run, and is the
#: default everywhere: an install on a hookless runtime keeps working.
GATE_RESPONSES = ("warn", "refuse")
DEFAULT_GATE_RESPONSE = "warn"

#: The staleness window the Start path has applied to the session marker since
#: MAR-1 (`skill-start.py` then, `acs step start` now). Read here only by
#: `accepted_session_marker`, which serves session CORRELATION; gate evidence has its own window below so that changing one
#: clock never moves the other.
SESSION_MARKER_MAX_AGE_SECONDS = 15 * 60

#: How long a hook fire's evidence answers for a run that starts after it.
#: Same duration as the marker's window today, declared separately on purpose.
GATE_EVIDENCE_MAX_AGE_SECONDS = 15 * 60

#: Every hooks/hooks.json binding, grouped under the enforcement it carries --
#: the notice's whole vocabulary. tests/acs/test_hook_gate_detection.py derives
#: the bindings from hooks.json itself, so a new one cannot go unnamed here.
HOOK_ENFORCEMENTS = (
    (("PreToolUse:Skill",), "precondition gate"),
    (("PreToolUse:Write|Edit|MultiEdit|NotebookEdit",), "file-map guard"),
    (("SubagentStart:^acs:", "SubagentStop:^acs:"), "phase-artifact validation"),
    (("Stop", "PreCompact", "SessionEnd"), "session bookkeeping"),
)


def gate_response(settings):
    """Resolve settings.hook_gates.when_absent; anything unrecognized is warn."""
    block = (settings or {}).get("hook_gates")
    value = block.get("when_absent") if isinstance(block, dict) else None
    return value if value in GATE_RESPONSES else DEFAULT_GATE_RESPONSE


def accepted_session_marker(ctx):
    """Read the pre-hook's session marker under the staleness/cross-session
    guard, returning (marker, None) or (None, why it was rejected)."""
    marker = read_json(
        session_marker_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"]))
    if not isinstance(marker, dict):
        return None, "no_gate_marker"
    if marker.get("checkout_id") != ctx["checkout_id"]:
        return None, "marker_foreign_checkout"
    updated_at = parse_iso(marker.get("updated_at"))
    if updated_at is None:
        return None, "marker_unparseable"
    if (datetime.now(timezone.utc) - updated_at).total_seconds() > SESSION_MARKER_MAX_AGE_SECONDS:
        return None, "marker_stale"
    return marker, None


def gate_evidence_path(workspace, repo_id, ckid):
    """Where the PreToolUse(Skill) hook records that it fired."""
    return os.path.join(sessions_dir(workspace, repo_id), "%s-gate.json" % ckid)


def record_gate_evidence(ctx, skill):
    """Write this fire's evidence, replacing any previous fire's.

    Carries only what gating needs -- the normalized entry point and when it
    fired. No correlation field appears here, by design: see the module
    docstring. A rewrite clears the previous consumption stamp by construction,
    because the whole document is replaced."""
    evidence = {
        "gate_skill": skill,
        "checkout_id": ctx["checkout_id"],
        "fired_at": now_iso(),
        "consumed_for": None,
    }
    write_json(
        gate_evidence_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"]),
        evidence)
    return evidence


def accepted_gate_evidence(ctx):
    """Read the gate artifact under the staleness/cross-checkout guard,
    returning (evidence, None) or (None, why it was rejected)."""
    evidence = read_json(
        gate_evidence_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"]))
    if not isinstance(evidence, dict):
        return None, "no_gate_evidence"
    if evidence.get("checkout_id") != ctx["checkout_id"]:
        return None, "evidence_foreign_checkout"
    fired_at = parse_iso(evidence.get("fired_at"))
    if fired_at is None:
        return None, "evidence_unparseable"
    if (datetime.now(timezone.utc) - fired_at).total_seconds() > GATE_EVIDENCE_MAX_AGE_SECONDS:
        return None, "evidence_stale"
    return evidence, None


def gate_evidence(ctx, skill):
    """Weigh the evidence that PreToolUse(Skill) fired for this `skill`.

    `gated` is true only on accepted evidence; false means no such evidence was
    found, which the fail-open write above makes weaker than "the gate did not
    fire". `reason` names the condition that decided it, and `unconfirmed` the
    enforcements this run cannot vouch for.

    Returns (evidence, verdict). The evidence comes back ONLY when the verdict
    is gated, since its single use is consume_gate_evidence -- nothing can stamp
    evidence the verdict rejected."""
    evidence, reason = accepted_gate_evidence(ctx)
    if evidence is not None:
        if evidence.get("gate_skill") != skill:
            reason = "evidence_for_other_skill"
        elif evidence.get("consumed_for") == evidence["fired_at"]:
            reason = "evidence_already_consumed"
    gated = evidence is not None and reason is None
    verdict = {
        "gated": gated,
        "reason": "gate_evidence_accepted" if gated else reason,
        "response": gate_response(ctx.get("settings")),
        # `unconfirmed`, not `not_in_force`: this run found no evidence for these
        # enforcements, which is not the same as establishing their absence.
        "unconfirmed": [] if gated else [name for _bindings, name in HOOK_ENFORCEMENTS],
        "notice": None,
        "checked_at": now_iso(),
    }
    verdict["notice"] = gate_notice(verdict)
    return (evidence if gated else None), verdict


def consume_gate_evidence(ctx, evidence):
    """Spend the evidence, so one hook fire gates exactly one run.

    The stamp records the instant it spent. A later genuine fire rewrites the
    whole artifact (`record_gate_evidence`), which clears the stamp by
    construction -- there is no arm that may preserve an older document,
    because this file holds nothing worth preserving."""
    spent = dict(evidence)
    spent["consumed_for"] = evidence["fired_at"]
    write_json(
        gate_evidence_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"]), spent)
    return spent


def gate_notice(verdict):
    """Render the degraded-enforcement notice for an unconfirmed verdict, else None."""
    if verdict.get("gated"):
        return None
    lines = [
        "acs: DEGRADED ENFORCEMENT — no evidence that the PreToolUse(Skill) gate "
        "fired for this run (%s)." % verdict.get("reason"),
        "The gate records that evidence fail-open (MAR-514: a marker-write bug "
        "must never block a gated skill), so a failed write looks exactly like a "
        "runtime that never fired the hook. What this run cannot confirm is in "
        "force:",
    ]
    for bindings, name in HOOK_ENFORCEMENTS:
        lines.append("  - %s (%s)" % (name, ", ".join(bindings)))
    lines.append(
        "Treat the run as ungated: a skill can start with an unmet predecessor, "
        "an executor can write outside its file map, and no phase artifact is "
        "validated.")
    if verdict.get("response") == "refuse":
        lines.append(
            "settings.hook_gates.when_absent is 'refuse', so this run is blocked "
            "on the absence of that evidence — which includes a gate that fired "
            "and could not record it. Run acs on a host that fires the hooks, or "
            "set the key to 'warn' to continue ungated.")
    else:
        lines.append(
            "settings.hook_gates.when_absent is 'warn' (the default), so this run "
            "continues ungated. Set the key to 'refuse' to block runs whose "
            "gating cannot be confirmed.")
    return "\n".join(lines)
