"""acs_lib.jobs — deterministic commands that run beside a skill's subagents (ADR-0125).

A coordinator that needs a long command — review-code's gate, create-impl-plan's
suite run — used to run it before or after its agents, so its wall-clock added to
theirs. A job runs it detached instead, started in the same turn as the spawn, and
the coordinator collects it when it needs the result:

    acs.py job start --name gate-lint -- ruff check .     returns at once
    (spawn the agents; they run while the job does)
    acs.py job wait --name gate-lint                      ONE blocking call

`wait` blocks inside one command until every named job has exited or the timeout
passes. That is not the polling a skill must never do — a model running `sleep`
in a loop pays a turn per tick and waits a fixed interval whatever happened; this
returns the moment the job ends.

Each job lives in `<run>/jobs/<name>.{json,log,exit}`: the record, its combined
output, and its exit code, written by the shell that ran it. The record is written
before the process starts and the exit file only after it ends, so a reader can
never see an exit code without a record.
"""

import json
import os
import re
import signal
import subprocess
import time

from ._common import GateError, now_iso

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
#: Below the Bash tool's 600 s ceiling, so one `wait` call always returns in time
#: for the caller to call it again.
DEFAULT_WAIT_SECONDS = 540
_TICK = 0.25


def jobs_dir(rdir):
    return os.path.join(rdir, "jobs")


def _paths(rdir, name):
    if not NAME_RE.match(name or ""):
        raise GateError("job name %r must be lowercase letters, digits, '-' or '_'" % (name,))
    base = os.path.join(jobs_dir(rdir), name)
    return base + ".json", base + ".log", base + ".exit"


def _exit_code(exit_path):
    try:
        with open(exit_path, encoding="utf-8") as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return None


def start(rdir, name, command, cwd):
    """Run `command` (a shell string) detached; return its record.

    A job of the same name that is still running is refused — two runs writing
    one log would leave neither readable. A finished one is replaced."""
    record_path, log_path, exit_path = _paths(rdir, name)
    if os.path.exists(record_path) and status(rdir, name)["state"] == "running":
        raise GateError("job %r is still running; wait for it or stop it first" % name)
    os.makedirs(jobs_dir(rdir), exist_ok=True)
    for path in (exit_path, log_path):
        if os.path.exists(path):
            os.remove(path)
    # The exit code is written by the same shell, after the command, through a
    # temp file renamed into place: a reader sees no file or a complete one.
    wrapped = '( %s ) >%s 2>&1; c=$?; printf "%%s" "$c" >%s.tmp && mv %s.tmp %s' % (
        command, _q(log_path), _q(exit_path), _q(exit_path), _q(exit_path))
    record = {"name": name, "command": command, "cwd": cwd, "started_at": now_iso(),
              "log": log_path}
    _write(record_path, record)
    # Double fork: a short-lived shell in a new session backgrounds the job and
    # prints its pid, so the job is nobody's child here -- it outlives this
    # process and is reaped by init, and its process group is the session's.
    launcher = subprocess.run(
        ["/bin/sh", "-c", "( %s ) </dev/null >/dev/null 2>&1 & echo $!" % wrapped],
        cwd=cwd, start_new_session=True, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=True)
    record["pid"] = int(launcher.stdout.strip())
    _write(record_path, record)
    return record


def status(rdir, name):
    """{name, state: running|passed|failed|stopped|missing, exit_code, ...}."""
    record_path, _log, exit_path = _paths(rdir, name)
    if not os.path.exists(record_path):
        return {"name": name, "state": "missing", "exit_code": None}
    with open(record_path, encoding="utf-8") as fh:
        record = json.load(fh)
    code = _exit_code(exit_path)
    if code is not None:
        state = "passed" if code == 0 else "failed"
    elif record.get("stopped_at"):
        state = "stopped"
    elif record.get("pid") and not _alive(record["pid"]):
        # Gone: either it just wrote its exit code (read it again) or it was
        # killed from outside before it could.
        code = _exit_code(exit_path)
        state = "stopped" if code is None else ("passed" if code == 0 else "failed")
    else:
        state = "running"
    return dict(record, state=state, exit_code=code)


def wait(rdir, names, timeout=DEFAULT_WAIT_SECONDS, clock=time.monotonic, sleep=time.sleep):
    """Block until every named job has ended or `timeout` seconds pass.
    Returns {"done": bool, "jobs": [status, ...]}; each status carries the last
    lines of its log."""
    deadline = clock() + timeout
    while True:
        states = [status(rdir, n) for n in names]
        if all(s["state"] != "running" for s in states) or clock() >= deadline:
            break
        sleep(_TICK)
    for s in states:
        s["tail"] = _tail(s.get("log"))
    return {"done": all(s["state"] != "running" for s in states), "jobs": states}


def stop(rdir, name):
    """Kill a running job's process group; a finished job is left as it is."""
    current = status(rdir, name)
    if current["state"] != "running":
        return current
    try:
        os.killpg(os.getpgid(current["pid"]), signal.SIGTERM)
    except (OSError, TypeError):
        pass
    record_path = _paths(rdir, name)[0]
    record = {k: v for k, v in current.items() if k not in ("state", "exit_code")}
    record["stopped_at"] = now_iso()
    _write(record_path, record)
    return dict(record, state="stopped", exit_code=None)


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _tail(path, lines=40):
    if not path or not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return "".join(fh.readlines()[-lines:])


def _q(path):
    return "'" + path.replace("'", "'\\''") + "'"


def _write(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
