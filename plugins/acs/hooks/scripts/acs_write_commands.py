"""acs_write_commands -- `acs.py write`: the one way a skill or an agent writes state (ADR-0136).

The workspace lives in `<git-common-dir>/acs/state-machine`. From a worktree
session Claude Code refuses an Edit/Write aimed at the main checkout, and the
Bash sandbox lets Bash write the main repo's shared `.git` directory but not the
main checkout -- so the Write tool can no longer reach a state file, while a
Bash call to this CLI can. Every result.json, iteration note, draft, report and
run-local document goes through here:

    python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write <path> [--append] [--run R] <<'ACS_EOF'
    ...content...
    ACS_EOF

`<path>` is absolute and inside the workspace root, or relative to the run dir
(`--run`, default this checkout's current run). Anything that resolves outside
the root -- a `..` escape, a symlinked directory or file -- is refused with
exit 2 and nothing is written, and so are the machine-owned ledgers, which
have verbs of their own. The write is atomic: a temp file in the target's
directory, then `os.replace`.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_cli import context_or_die, die, emit  # noqa: E402

COMMAND = "write"

#: Files acs's own state machines own, with the verb that writes each. A
#: model-authored copy would bypass the machine that keeps them consistent
#: (and `active-agents/` + `filemap.json` are the file-map guard's control
#: inputs, which an executor must never be able to answer for itself).
OWNED_BASENAMES = {
    "run.json": "acs.py run / acs.py step",
    "lock.json": "acs.py lock (and the pre-hook)",
    "filemap.json": "acs.py filemap set",
    "runs-index.json": "acs.py run new",
    "tickets-index.json": "acs.py ticket save",
}
OWNED_DIRS = {
    "active-agents": "the SubagentStart hook",
    "sessions": "acs.py step start / the session hooks",
}


def _owner(rel_parts):
    """The verb that owns this workspace-relative path, or None."""
    name = rel_parts[-1]
    if name in OWNED_BASENAMES:
        return OWNED_BASENAMES[name]
    if name == "state.json" and len(rel_parts) >= 3 and rel_parts[-3] == "steps":
        return "acs.py step start / finish"
    if "active-agents" in rel_parts[:-1]:
        return OWNED_DIRS["active-agents"]
    if len(rel_parts) > 2 and rel_parts[1] == "sessions":   # <repo-id>/sessions/...
        return OWNED_DIRS["sessions"]
    return None


def _run_dir(ctx, explicit):
    run_id = explicit or lib.current_run_id(ctx)
    if not run_id:
        die(COMMAND, "no current run for this checkout, and no --run given: pass an "
                     "absolute path inside the workspace (%s), or name the run with "
                     "--run." % ctx["workspace"])
    rdir = lib.run_dir(lib.repo_dir(ctx["workspace"], ctx["repo_id"]), run_id)
    if lib.load_run(rdir) is None:
        die(COMMAND, "no run %r (expected %s)" % (run_id, rdir))
    return rdir


def _inside(path, root):
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def resolve_target(ctx, raw, run=None):
    """(real target path, workspace-relative parts). Exits 2 on any refusal."""
    root = os.path.realpath(ctx["workspace"])
    if os.path.isabs(raw):
        joined = os.path.normpath(raw)
    else:
        joined = os.path.normpath(os.path.join(_run_dir(ctx, run), raw))
    # realpath resolves every symlink on the way, the final component included:
    # a link anywhere in the chain that leads out of the root is an escape.
    target = os.path.realpath(joined)
    if not _inside(target, root) or target == root:
        die(COMMAND, "%s resolves to %s, outside the workspace root %s -- acs.py write "
                     "writes state only; write repo files with the Write tool."
            % (raw, target, root))
    if os.path.isdir(target):
        die(COMMAND, "%s is a directory, not a file" % target)
    rel = os.path.relpath(target, root).split(os.sep)
    owner = _owner(rel)
    if owner:
        die(COMMAND, "%s is machine-owned state; it is written by %s, never by "
                     "acs.py write." % (target, owner))
    return target, rel


def _read_stdin():
    if sys.stdin is None or sys.stdin.isatty():
        die(COMMAND, "expected the content on stdin -- use a quoted heredoc: "
                     "acs.py write <path> <<'ACS_EOF' ... ACS_EOF")
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is not None:
        return buffer.read()
    return sys.stdin.read().encode("utf-8")


def atomic_write(target, data, append=False):
    """Write `data` (bytes) to target via a temp file + os.replace; returns the
    file's size afterwards. On any failure the target is left as it was.

    Held under a per-file O_EXCL guard (`repo_guard`), because `--append` is a
    read-modify-write: parallel adjudicators appending to one file would
    otherwise each read the same old content and the last replace would drop
    the others' lines."""
    parent = os.path.dirname(target)
    os.makedirs(parent, exist_ok=True)
    guard = ".%s.write.guard" % os.path.basename(target)
    with lib.repo_guard(parent, guard):
        return _replace(target, parent, data, append)


def _replace(target, parent, data, append):
    prior = b""
    if append and os.path.exists(target):
        with open(target, "rb") as fh:
            prior = fh.read()
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".acs-tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(prior)
            fh.write(data)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return len(prior) + len(data)


def cmd_write(args):
    ctx = context_or_die(COMMAND)
    target, _rel = resolve_target(ctx, args.path, args.run)
    data = _read_stdin()
    try:
        total = atomic_write(target, data, append=args.append)
    except (OSError, lib.GateError) as exc:
        die(COMMAND, "could not write %s (%s); the file was left as it was" % (target, exc))
    emit({"ok": True, "path": target, "bytes": len(data), "appended": bool(args.append),
          "total_bytes": total})


def add_parser(group):
    write = group(COMMAND, help="write a workspace state file from stdin, atomically "
                                "(the Write tool cannot reach the workspace; ADR-0136)")
    write.add_argument("path", help="absolute inside the workspace root, or relative to "
                                    "the run dir")
    write.add_argument("--append", action="store_true",
                       help="append to the file instead of replacing it")
    write.add_argument("--run", help="the run a relative path is under (default: this "
                                     "checkout's current run)")
    write.set_defaults(func=cmd_write)
