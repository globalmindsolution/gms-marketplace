"""acs_lib.team_handoff_receive — pick up a ticket another member handed off (ADR-0131).

The receiving half of `acs_lib.team_handoff`. In order, and refusing before
anything is written:

  1. fetch `refs/acs/handoff/<ID>` and read its manifest;
  2. refuse when this workspace already holds the ticket's run or ticket
     partition (unless --replace, which moves them to a backup first);
  3. refuse a dirty working tree -- the work is applied onto a clean checkout;
  4. merge `git diff --binary <base> <work> | git apply --3way --cached` in
     a TEMPORARY index, so a conflict is reported with its paths while the
     checkout is still untouched;
  5. write only the paths that merge changed into the working tree, through
     a temporary index -- never `reset` or `clean`: the real index, HEAD's
     reflog and every untracked or ignored file stay as they were, and the
     work ends up uncommitted and unstaged, as the sender had it;
  6. restore the resume set, rewriting the path tokens to this machine's paths;
  7. upsert tickets-index / runs-index, raise counters.next to at least the
     sender's, point this checkout at the run;
  8. keep the commit under `refs/acs/received/<ID>` (its trees stay
     reachable) and delete the remote ref unless --keep-ref.
"""

import os
import shutil
import subprocess
import tempfile

from ._common import GateError, _ensure_state_root_ignored, now_iso, read_json, write_json
from .changes import _run_git, drop_new_gitlinks, empty_tree, head_sha, name_status
from .repo import repo_dir, repo_guard, ticket_dir
from . import run as run_mod
from . import sessions
from . import team_handoff as th

MANIFEST_SCHEMA = "handoff-manifest.schema.json"


def _validate_manifest(manifest, ticket_id):
    from .schemasubset import schema_errors
    from .skills import load_schema
    if manifest is None:
        raise GateError("the handoff of %s carries no readable manifest.json" % ticket_id)
    errors = schema_errors(load_schema(MANIFEST_SCHEMA), manifest)
    if errors:
        raise GateError("the handoff manifest is not valid: %s" % "; ".join(
            "%s: %s" % (path or "/", msg) for path, msg in errors[:5]))
    if manifest.get("format") != th.FORMAT:
        raise GateError("the handoff was written in format %r; this acs reads format %d -- "
                        "update acs on one side" % (manifest.get("format"), th.FORMAT))
    if manifest.get("ticket") != ticket_id:
        raise GateError("refs/acs/handoff/%s carries a handoff of %s"
                        % (ticket_id, manifest.get("ticket")))


def _dirty_paths(root):
    # GIT_OPTIONAL_LOCKS=0: a read, so git must not refresh-write the index.
    raw = _run_git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
                   env={"GIT_OPTIONAL_LOCKS": "0"}).stdout
    return [rec[3:] for rec in raw.decode("utf-8", "surrogateescape").split("\0")
            if len(rec) > 3 and rec[2] == " "]


def _tree_at(root, commit, path):
    proc = _run_git(root, ["rev-parse", "--verify", "--quiet", "%s:%s" % (commit, path)],
                    check=False)
    return proc.stdout.decode().strip() if proc.returncode == 0 else None


def work_patch(root, base, work):
    """`git diff --binary <base> <work>` -- the sender's whole changeset."""
    return _run_git(root, ["diff", "--binary", "--no-renames", "--no-ext-diff",
                           base, work]).stdout


def _apply_cached(root, patch, env):
    """`git apply --3way --cached`: the index named by `env` only."""
    return subprocess.run(["git", "apply", "--3way", "--cached"], cwd=root, input=patch,
                          capture_output=True, env=dict(os.environ, **env))


def merge_patch(root, patch):
    """Apply `patch` with a 3-way fallback to a TEMPORARY index built from
    HEAD. Returns (merged tree id, []) when it applies, (None, conflicting
    paths) when it does not. The checkout, its index and HEAD are never
    touched -- this is both the dry run and the merge itself. A gitlink HEAD
    does not track (a nested worktree an older sender packaged) is dropped."""
    tmpdir = tempfile.mkdtemp(prefix="acs-receive-")
    try:
        env = {"GIT_INDEX_FILE": os.path.join(tmpdir, "index")}
        has_head = head_sha(root)
        _run_git(root, ["read-tree", "HEAD"] if has_head else ["read-tree", "--empty"],
                 env=env)
        proc = _apply_cached(root, patch, env)
        if proc.returncode == 0:
            drop_new_gitlinks(root, env, "HEAD" if has_head else None)
            return _run_git(root, ["write-tree"], env=env).stdout.decode().strip(), []
        raw = _run_git(root, ["ls-files", "-u", "-z"], env=env).stdout
        paths = sorted({rec.split("\t", 1)[1] for rec in
                        raw.decode("utf-8", "surrogateescape").split("\0") if "\t" in rec})
        if not paths:
            raise GateError("the handoff's work does not apply here: %s"
                            % proc.stderr.decode("utf-8", "replace").strip())
        return None, paths
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def apply_work(root, merged):
    """Write the merged tree's changes into the working tree -- and nothing
    else. Only the paths that differ between HEAD and `merged` are written or
    removed, through a TEMPORARY index (`checkout-index`), so the real index,
    HEAD, its reflog and every other file -- untracked or ignored -- are left
    exactly as they were. No reset, no clean: the receiver gets the work the
    way the sender had it, uncommitted and unstaged. Returns the paths."""
    base = _run_git(root, ["rev-parse", "HEAD^{tree}"]).stdout.decode().strip() \
        if head_sha(root) else empty_tree(root)
    entries = name_status(root, base, merged)
    write = [e["path"] for e in entries if e["status"] != "deleted"]
    tmpdir = tempfile.mkdtemp(prefix="acs-receive-")
    try:
        env = {"GIT_INDEX_FILE": os.path.join(tmpdir, "index")}
        _run_git(root, ["read-tree", merged], env=env)
        if write:
            proc = subprocess.run(["git", "checkout-index", "-f", "-z", "--stdin"], cwd=root,
                                  input=("\0".join(write) + "\0").encode("utf-8",
                                                                         "surrogateescape"),
                                  capture_output=True, env=dict(os.environ, **env))
            if proc.returncode != 0:
                raise GateError("writing the handoff's work failed: %s"
                                % proc.stderr.decode("utf-8", "replace").strip())
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    for entry in entries:
        if entry["status"] == "deleted":
            path = os.path.join(root, entry["path"])
            if os.path.lexists(path):
                os.remove(path)
            parent = os.path.dirname(path)
            while parent != root and os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
                parent = os.path.dirname(parent)
    return [e["path"] for e in entries]


def _package_entries(root, commit):
    """{package path: blob id} for the files under acs/ and attachments/."""
    raw = _run_git(root, ["ls-tree", "-r", "-z", "--full-tree", commit]).stdout
    out = {}
    for rec in raw.decode("utf-8", "surrogateescape").split("\0"):
        if "\t" not in rec:
            continue
        meta, path = rec.split("\t", 1)
        if path.startswith(("acs/", "attachments/")):
            out[path] = meta.split()[2]
    return out


def _destination(pkg, tdir, rdir):
    if pkg.startswith("acs/ticket/"):
        return os.path.join(tdir, pkg[len("acs/ticket/"):])
    if pkg.startswith("acs/run/") and rdir:
        return os.path.join(rdir, pkg[len("acs/run/"):])
    if pkg.startswith("attachments/") and rdir:
        return os.path.join(run_mod.subject_dir(rdir), os.path.basename(pkg))
    return None


def _write_bytes(path, data):
    _ensure_state_root_ignored(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".acs-tmp-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def restore(root, commit, tdir, rdir, paths):
    """Write the resume set and the attachments; returns what was written."""
    written = []
    for pkg, blob in sorted(_package_entries(root, commit).items()):
        dest = _destination(pkg, tdir, rdir)
        if dest is None:
            continue
        data = _run_git(root, ["cat-file", "blob", blob]).stdout
        if pkg.startswith("acs/"):
            try:
                data = th.from_tokens(data.decode("utf-8"), paths).encode("utf-8")
            except UnicodeDecodeError:
                pass
        _write_bytes(dest, data)
        written.append(pkg)
    return written


def _existing(tdir, rdir):
    found = []
    if rdir and os.path.isdir(rdir):
        found.append(("run", rdir))
    if os.path.isfile(os.path.join(tdir, "ticket.json")):
        found.append(("ticket", tdir))
    return found


def backup(rpath, ticket_id, existing):
    """Move each existing directory under handoff-backups/<ID>-<stamp>/."""
    stamp = now_iso().replace(":", "").replace("-", "")
    dest = os.path.join(rpath, "handoff-backups", "%s-%s" % (ticket_id, stamp))
    n = 1
    while os.path.exists(dest):
        n += 1
        dest = os.path.join(rpath, "handoff-backups", "%s-%s-%d" % (ticket_id, stamp, n))
    os.makedirs(dest)
    for kind, path in existing:
        shutil.move(path, os.path.join(dest, kind))
    return dest


def raise_counters(rpath, floor):
    """counters.next := max(local, sender's). A fresh workspace adopts the
    sender's (reconciled -- the sender's counter already was)."""
    if not isinstance(floor, int) or floor < 1:
        return None
    with repo_guard(rpath, "counters.json.lock"):
        path = os.path.join(rpath, "counters.json")
        doc = read_json(path)
        doc = doc if isinstance(doc, dict) else {}
        current = doc.get("next") if isinstance(doc.get("next"), int) else None
        if current is not None and current >= floor:
            return current
        doc["next"] = floor
        if current is None:
            doc.update(reconciled=True, seed_source="handoff", seeded_at=now_iso())
        write_json(path, doc)
        return floor


def continue_with(ctx, ticket_id, doc):
    """(next step or None, the command to continue with)."""
    if not doc:
        return None, "/acs:ship %s" % ticket_id
    step = run_mod.in_progress_step(doc)
    if step is None:
        stopped = [(entry.get("ended_at") or "", name)
                   for name, entry in (doc.get("steps") or {}).items()
                   if (entry or {}).get("status") == "interrupted"]
        step = max(stopped)[1] if stopped else None
    if step is None and doc.get("status") not in run_mod.TERMINAL_RUN_STATUSES:
        try:
            from .workflow import resolve_workflow, validate_workflow_file
            wf = validate_workflow_file(resolve_workflow(ctx.get("checkout_root"))["path"])
            step = run_mod.cursor(doc, wf)
        except Exception:  # noqa: BLE001 -- a hint, never a reason to fail a receive
            step = None
    return step, ("/acs:%s %s" % (step, ticket_id) if step else "/acs:ship %s" % ticket_id)


def receive(ctx, ticket_id, replace=False, keep_ref=False, remote="origin"):
    """Fetch, check, apply and restore a handoff. Returns the CLI's report."""
    from .tickets import load_ticket, update_index
    root = ctx["checkout_root"]
    th.check_ticket_id(ticket_id, (ctx.get("settings") or {}).get("ticket_prefix"))
    ref = th.handoff_ref(ticket_id)
    if th.remote_ref_sha(root, remote, ref) is None:
        raise GateError("no handoff of %s is waiting on %s (%s does not exist) -- "
                        "`acs.py handoff list` shows the ones that are" % (ticket_id, remote, ref))
    commit = th.fetch_ref(root, remote, ref)
    manifest = th.read_manifest(root, commit)
    _validate_manifest(manifest, ticket_id)
    rpath = repo_dir(ctx["workspace"], ctx["repo_id"])
    run_id = manifest.get("run_id")
    tdir = ticket_dir(ctx["workspace"], ctx["repo_id"], ticket_id)
    rdir = run_mod.run_dir(rpath, run_id) if run_id else None
    existing = _existing(tdir, rdir)
    if existing and not replace:
        raise GateError("this workspace already holds %s (%s) -- pass --replace to move it to "
                        "a backup and take the handoff" % (ticket_id, ", ".join(
                            "%s %s" % (kind, path) for kind, path in existing)))
    dirty = _dirty_paths(root)
    if dirty:
        raise GateError("the working tree is not clean (%s%s) -- commit, stash or discard "
                        "those changes first; a handoff's work applies onto a clean checkout"
                        % (", ".join(dirty[:5]), ", ..." if len(dirty) > 5 else ""))
    base = manifest.get("base_sha") or empty_tree(root)
    work = _tree_at(root, commit, "work") or empty_tree(root)
    patch = work_patch(root, base, work)
    if patch.strip():
        merged, conflicts = merge_patch(root, patch)
        if conflicts:
            raise GateError(
                "the handoff's work conflicts with this checkout in: %s. Nothing was changed. "
                "Check out the sender's base (git switch -c <branch> %s) and receive again, "
                "or reconcile those files first."
                % (", ".join(conflicts), (manifest.get("base_sha") or "")[:12]))
        apply_work(root, merged)
    backed_up = backup(rpath, ticket_id, existing) if existing else None
    written = restore(root, commit, tdir, rdir, th.local_paths(ctx, rdir))
    ticket = load_ticket(tdir)
    if isinstance(ticket, dict) and ticket.get("id"):
        update_index(ctx["workspace"], ctx["repo_id"], ticket)
    doc = run_mod.load_run(rdir) if rdir else None
    if doc is not None:
        run_mod.index_run(rpath, doc)
    counters = raise_counters(rpath, manifest.get("counters_next"))
    if doc is not None:
        sessions.save_pointer(rpath, ctx["checkout_id"], run_id=run_id,
                              checkout_path=root)
    _run_git(root, ["update-ref", th.RECEIVED_PREFIX + ticket_id, commit])
    deleted, delete_error = (False, None)
    if not keep_ref:
        deleted, delete_error = th.delete_ref(root, remote, ref, commit)
    step, command = continue_with(ctx, ticket_id, doc)
    return {
        "ok": True, "ticket": ticket_id, "run_id": run_id, "commit": commit,
        "sender": manifest.get("sender"), "sent_at": manifest.get("sent_at"),
        "sender_branch": manifest.get("branch"), "base_sha": manifest.get("base_sha"),
        "note": th.read_note(root, commit).strip(),
        "work_applied": bool(patch.strip()),
        "work_changes": name_status(root, base, work),
        "restored": written,
        "attachments": [a.get("ref") for a in manifest.get("attachments") or []],
        "withheld_attachments": [a.get("ref") for a in
                                 manifest.get("withheld_attachments") or []],
        "backup": backed_up, "counters_next": counters,
        "kept_ref": th.RECEIVED_PREFIX + ticket_id,
        "ref_deleted": deleted, "ref_delete_error": delete_error or None,
        "steps": dict((name, (entry or {}).get("status"))
                      for name, entry in ((doc or {}).get("steps") or {}).items()),
        "manifest": manifest,
        "next_step": step, "continue_with": command,
    }
