"""acs_lib.hostgates — does this runtime actually fire acs's hooks?

acs's enforcement is carried entirely by the hooks `hooks/hooks.json` binds to
Claude Code lifecycle events. On a host that does not raise those events none of
it runs: a skill can start with an unmet predecessor, an executor can write
outside its file map, and no phase artifact is validated. The skills still read
as instructions, so a pipeline appears to execute and nothing says otherwise.

This module makes that state answerable at runtime, from evidence rather than
inference. `run_pre_payload` records the session marker (`repo.record_session_
marker`) as its FIRST action, before the gate itself passes or blocks, and the
only other caller passes `record_marker=False` precisely so `acs.py gate` cannot
forge one. The marker is therefore written by the PreToolUse(Skill) hook and by
nothing else: if it is there the kernel ran the gate, and if it is not, it did
not. The detection is exactly as accurate as the gate it reports on.

Three conditions make the evidence answer for THIS invocation rather than some
earlier one: the marker is fresh and belongs to this checkout, it was recorded
for this entry-point skill, and it has not already been spent by another run
(`consume_gate_evidence`). Anything else is reported ungated with the reason
that says which condition failed -- never silently.
"""

from datetime import datetime, timezone

from ._common import now_iso, parse_iso, read_json, write_json
from .repo import session_marker_path

#: settings.hook_gates.when_absent. `warn` never blocks a run, and is the
#: default everywhere: an install on a hookless runtime keeps working.
GATE_RESPONSES = ("warn", "refuse")
DEFAULT_GATE_RESPONSE = "warn"

#: The staleness window skill-start.py has applied to the session marker since
#: MAR-1; evidence older than this belongs to some earlier session.
SESSION_MARKER_MAX_AGE_SECONDS = 15 * 60

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


def gate_evidence(ctx, skill):
    """Decide whether PreToolUse(Skill) fired for this invocation of `skill`.

    Returns (marker, verdict). The marker comes back ONLY when the verdict is
    gated, since its single use is consume_gate_evidence -- nothing can stamp
    evidence the verdict rejected."""
    marker, reason = accepted_session_marker(ctx)
    if marker is not None:
        if marker.get("gate_skill") is None:
            # A marker written by an acs older than MAR-583 names no entry
            # point: ungated is the honest answer, and the next hook fire
            # corrects it.
            reason = "marker_predates_gate_evidence"
        elif marker["gate_skill"] != skill:
            reason = "marker_for_other_skill"
        elif marker.get("gate_consumed_for") == marker["updated_at"]:
            reason = "marker_already_consumed"
    gated = marker is not None and reason is None
    verdict = {
        "gated": gated,
        "reason": "gate_marker_accepted" if gated else reason,
        "response": gate_response(ctx.get("settings")),
        "not_in_force": [] if gated else [name for _bindings, name in HOOK_ENFORCEMENTS],
        "notice": None,
        "checked_at": now_iso(),
    }
    verdict["notice"] = gate_notice(verdict)
    return (marker if gated else None), verdict


def consume_gate_evidence(ctx, marker):
    """Spend the marker, so one hook fire gates exactly one run.

    A genuine new hook fire rewrites the whole marker and clears the stamp by
    construction (repo.record_session_marker writes, never merges)."""
    spent = dict(marker)
    spent["gate_consumed_for"] = marker["updated_at"]
    write_json(
        session_marker_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"]), spent)
    return spent


def gate_notice(verdict):
    """Render the degraded-enforcement notice for an ungated verdict, else None."""
    if verdict.get("gated"):
        return None
    lines = [
        "acs: DEGRADED ENFORCEMENT — the PreToolUse(Skill) gate did not fire for "
        "this run (%s)." % verdict.get("reason"),
        "This runtime is not enforcing acs's hooks. NOT in force for this run:",
    ]
    for bindings, name in HOOK_ENFORCEMENTS:
        lines.append("  - %s (%s)" % (name, ", ".join(bindings)))
    lines.append(
        "A skill can start with an unmet predecessor, an executor can write "
        "outside its file map, and no phase artifact is validated.")
    if verdict.get("response") == "refuse":
        lines.append(
            "settings.hook_gates.when_absent is 'refuse', so this run is blocked. "
            "Run acs on a host that fires the hooks, or set the key to 'warn' to "
            "continue ungated.")
    else:
        lines.append(
            "settings.hook_gates.when_absent is 'warn' (the default), so this run "
            "continues ungated. Set the key to 'refuse' to block runs the gates "
            "do not cover.")
    return "\n".join(lines)
