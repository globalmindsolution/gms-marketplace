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

#: How long to wait for the in-process bound to unwind before killing the
#: process outright. Only reached when the alarm was raised and something
#: swallowed it anyway.
GATE_HARD_TIMEOUT_SECONDS = 5


class GateTimeout(BaseException):
    """Raised into a gate that overran its bound.

    Deliberately a BaseException, not TimeoutError. TimeoutError subclasses
    OSError, and the gate path is full of `except OSError` / `except Exception`
    handlers that legitimately swallow their own errors -- acs_lib._git returns
    None on OSError, record_session_marker passes on Exception. Either would
    absorb the alarm and let an unbounded gate run on to return 0, which reads
    as "not blocked". Nothing catches a bare BaseException by accident.
    """


def run_gate(skill, payload):
    """Run the skill's gate in-process, bounded, and fail closed.

    The bound matters because the hook's own timeout kills this process without
    an exit code of 2, which reads as "not blocked"."""
    if not hasattr(signal, "SIGALRM"):  # no POSIX alarms (Windows)
        # Unbounded, so the timeout guarantee does not hold here. Fail closed on
        # anything raised rather than letting it escape as a non-2 exit.
        try:
            return acs_lib.run_pre_payload(skill, payload)
        except BaseException as exc:  # noqa: BLE001 - a gate must not fail open
            sys.stderr.write("acs pre-%s: blocked — gate raised %r\n" % (skill, exc))
            return 2

    def _on_timeout(_signum, _frame):
        # Re-arm: if this raise is swallowed by a broad handler inside the gate,
        # the next alarm turns the hard-timeout handler into a process kill.
        signal.signal(signal.SIGALRM, _on_hard_timeout)
        signal.alarm(GATE_HARD_TIMEOUT_SECONDS)
        raise GateTimeout("gate for %s exceeded %ds" % (skill, GATE_TIMEOUT_SECONDS))

    def _on_hard_timeout(_signum, _frame):
        # The bound was swallowed. Exit 2 directly -- os._exit skips the
        # cleanup an exception would run, none of which can help here.
        sys.stderr.write(
            "acs pre-%s: blocked — gate ignored its %ds bound\n"
            % (skill, GATE_TIMEOUT_SECONDS))
        sys.stderr.flush()
        os._exit(2)

    previous = signal.signal(signal.SIGALRM, _on_timeout)
    signal.alarm(GATE_TIMEOUT_SECONDS)
    try:
        return acs_lib.run_pre_payload(skill, payload)
    except GateTimeout as exc:
        sys.stderr.write("acs pre-%s: blocked — gate timed out: %s\n" % (skill, exc))
        return 2
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
