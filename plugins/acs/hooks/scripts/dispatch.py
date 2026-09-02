#!/usr/bin/env python3
"""dispatch.py — single hook entry point for the acs plugin.

Registered in hooks/hooks.json:
  * `dispatch.py pre`         on PreToolUse (matcher: Skill) — runs the skill's gate
    in-process. Exit 2 blocks the skill; its stderr explains what to run first. The
    gate is bounded by GATE_TIMEOUT_SECONDS and fails closed on timeout or error,
    because any exit code other than 2 lets the skill run.
  * `dispatch.py session-end` on SessionEnd — finalizes runs left in_progress by this
    checkout as `interrupted` and releases the ticket lock.

The dispatcher itself never gates: skills that are not part of the acs pipeline
(or acs skills without hooks: setup, ship, handoff) pass through with exit 0.
"""

import json
import os
import signal
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import acs_lib  # noqa: E402


def skill_name_from_payload(payload):
    tool_input = payload.get("tool_input") or {}
    for key in ("skill", "skill_name", "name", "command"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            name = value.strip()
            # plugin skills are namespaced (acs:create-ticket); strip the namespace
            if ":" in name:
                prefix, _, rest = name.partition(":")
                if prefix != "acs":
                    return None  # another plugin's skill — not ours to gate
                name = rest
            return name.lstrip("/").strip()
    return None


#: A gate is a few git calls and some JSON reads; anything longer is stuck.
GATE_TIMEOUT_SECONDS = 25


def run_gate(skill, payload):
    """Run the skill's gate in-process, bounded, and fail closed.

    The bound matters because the hook's own timeout kills this process without
    an exit code of 2, which reads as "not blocked"."""
    if not hasattr(signal, "SIGALRM"):  # no POSIX alarms (Windows): run unbounded
        return acs_lib.run_pre_payload(skill, payload)

    def _on_timeout(_signum, _frame):
        raise TimeoutError("gate for %s exceeded %ds" % (skill, GATE_TIMEOUT_SECONDS))

    previous = signal.signal(signal.SIGALRM, _on_timeout)
    signal.alarm(GATE_TIMEOUT_SECONDS)
    try:
        return acs_lib.run_pre_payload(skill, payload)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "pre"
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    if mode == "session-end":
        try:
            acs_lib.session_end(payload)
        except Exception as exc:  # cleanup must never break session teardown
            sys.stderr.write("acs session-end: %r\n" % exc)
        sys.exit(0)

    skill = skill_name_from_payload(payload)
    if skill not in acs_lib.HOOKED_SKILLS:
        sys.exit(0)

    sys.exit(run_gate(skill, payload))


if __name__ == "__main__":
    main()
