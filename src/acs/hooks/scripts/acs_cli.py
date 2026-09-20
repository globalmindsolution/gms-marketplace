"""acs_cli — the shared helpers every acs.py subcommand uses.

Split out of acs.py by MAR-572, which is code motion only. acs.py grew a
command group per ticket (MAR-521's groups, then readiness, pr and tracker)
until it crossed E1's 800-line budget; the handlers moved to acs_commands and
the helpers they share moved here, so neither module has to import the entry
point back.

The stdout/stderr contract lives here and nowhere else: exactly one pretty
JSON object on stdout, and `acs <command>: <reason>` with exit 2 for a usage
or precondition failure.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def emit(obj):
    """The one stdout contract: a single pretty JSON object."""
    print(json.dumps(obj, indent=2, sort_keys=True))


def die(command, reason, code=2):
    sys.stderr.write("acs %s: %s\n" % (command, reason))
    sys.exit(code)


def context_or_die(command):
    try:
        return lib.build_context(os.getcwd())
    except lib.GateError as exc:
        die(command, str(exc))


def partition_or_die(command, explicit):
    """Resolve (ticket_id, tdir, ctx) for an ACTIVE partition, or exit 2.

    The resolution itself lives in acs_lib.resolve_active_partition, shared with
    clarify.py and plan-approval.py — this only turns its GateError into the
    CLI's `acs <command>: <reason>` + exit 2."""
    ctx = context_or_die(command)
    try:
        ticket_id, tdir, _archived = lib.resolve_active_partition(
            os.getcwd(), ctx, explicit=explicit)
    except lib.GateError as exc:
        die(command, str(exc))
    return ticket_id, tdir, ctx


def run_or_die(command, explicit=None):
    """Resolve (run_id, rdir, ctx) for THIS CHECKOUT'S run, or exit 2.

    The run-scoped commands -- filemap, guard, verdict -- take no --ticket any
    more: the partition is a run (§4.2), the checkout's pointer names it, and
    `--run` exists only to name another. A ticket id still works, because a
    ticket run's id IS the ticket id."""
    ctx = context_or_die(command)
    run_id = explicit or lib.current_run_id(ctx)
    if not run_id:
        die(command, "no current run for this checkout, and no --run given. "
                     "Start one by invoking a skill with a ticket id, a prompt or a "
                     "document, or name an existing run with --run.")
    rdir = lib.run_dir(lib.repo_dir(ctx["workspace"], ctx["repo_id"]), run_id)
    if lib.load_run(rdir) is None:
        die(command, "no run %r (expected %s)" % (run_id, rdir))
    return run_id, rdir, ctx


def load_ticket_or_die(command, tdir, ticket_id):
    ticket = lib.load_ticket(tdir)
    if not isinstance(ticket, dict):
        die(command, "no readable ticket.json for %s" % ticket_id)
    return ticket


def read_json_arg(command, path):
    """A JSON object from `path`, or from stdin when path is absent or '-'."""
    if path and path != "-":
        data = lib.read_json(path)
        if not isinstance(data, dict):
            die(command, "%s is missing or not a JSON object" % path)
        return data
    if sys.stdin.isatty():
        die(command, "expected a JSON object on stdin (or pass a file)")
    raw = sys.stdin.read().strip()
    if not raw:
        die(command, "expected a JSON object on stdin, got nothing")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        die(command, "invalid JSON on stdin: %s" % exc)
    if not isinstance(data, dict):
        die(command, "expected a JSON object on stdin, got %s" % type(data).__name__)
    return data
