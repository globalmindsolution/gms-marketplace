"""acs_job_commands — `acs.py job ...`, commands that run beside a skill's subagents (ADR-0125).

    acs.py job start  --name N [--cwd DIR] -- <command ...>   detached; returns at once
    acs.py job wait   --name N [--name M ...] [--timeout S]   ONE blocking call until all end
    acs.py job status --name N [--name M ...]                 running|passed|failed|stopped|missing
    acs.py job stop   --name N                                kill a running job

Jobs belong to this checkout's current run (or `--run`), under `<run>/jobs/`.
`wait` exits 0 when every job passed, 1 when one failed or was stopped, and 3
when the timeout passed with a job still running — call it again; never poll
with `sleep`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_cli import emit  # noqa: E402
from acs_state_commands import _resolve_run  # noqa: E402

J = lib.jobs


def _rdir(command, args):
    rdir, _doc, ctx, _wf = _resolve_run(command, args.run)
    return rdir, ctx


def cmd_job_start(args):
    rdir, ctx = _rdir("job start", args)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise lib.GateError("job start needs a command after --")
    shell = command[0] if len(command) == 1 else " ".join(_quote(c) for c in command)
    cwd = args.cwd or ctx.get("checkout_root") or os.getcwd()
    emit({"ok": True, "job": J.start(rdir, args.name, shell, cwd)})


def cmd_job_wait(args):
    rdir, _ctx = _rdir("job wait", args)
    out = J.wait(rdir, args.name, timeout=args.timeout)
    emit(dict(out, ok=out["done"] and all(j["state"] == "passed" for j in out["jobs"])))
    if not out["done"]:
        sys.exit(3)
    if any(j["state"] != "passed" for j in out["jobs"]):
        sys.exit(1)


def cmd_job_status(args):
    rdir, _ctx = _rdir("job status", args)
    emit({"ok": True, "jobs": [J.status(rdir, n) for n in args.name]})


def cmd_job_stop(args):
    rdir, _ctx = _rdir("job stop", args)
    emit({"ok": True, "job": J.stop(rdir, args.name)})


def _quote(arg):
    safe = all(c.isalnum() or c in "-_./=:,@%+" for c in arg)
    return arg if arg and safe else "'" + arg.replace("'", "'\\''") + "'"


def add_parser(group):
    job = group("job", help="deterministic commands that run beside a skill's subagents")
    sub = job.add_subparsers(dest="verb")

    start = sub.add_parser("start", help="run a command detached; returns at once")
    start.add_argument("--name", required=True)
    start.add_argument("--cwd")
    start.add_argument("--run")
    start.add_argument("command", nargs="...", help="-- then the command (one shell string, "
                                                    "or the words of one)")
    start.set_defaults(func=cmd_job_start)

    wait = sub.add_parser("wait", help="block until the named jobs end")
    wait.add_argument("--name", required=True, action="append")
    wait.add_argument("--timeout", type=float, default=J.DEFAULT_WAIT_SECONDS)
    wait.add_argument("--run")
    wait.set_defaults(func=cmd_job_wait)

    status = sub.add_parser("status", help="the named jobs' state, without waiting")
    status.add_argument("--name", required=True, action="append")
    status.add_argument("--run")
    status.set_defaults(func=cmd_job_status)

    stop = sub.add_parser("stop", help="kill a running job")
    stop.add_argument("--name", required=True)
    stop.add_argument("--run")
    stop.set_defaults(func=cmd_job_stop)
