"""acs_lib.team_handoff — hand a TICKET from one member's machine to another's (ADR-0131).

A ticket's work is two things: the uncommitted changes in the sender's working
tree, and the run's state in the workspace outside the repo. Neither travels by
itself -- the workspace is gitignored and machine-local, and only
`/acs:create-pr` commits (ADR-0127). A handoff packages both into ONE commit on
the hidden ref `refs/acs/handoff/<ID>`, never on a branch:

    <commit>  parent = the run's baseline.base_sha (HEAD when there is none)
      work/          the working-tree snapshot (`changes.snapshot`): tracked
                     edits, deletions and untracked non-ignored files
      acs/ticket/    ticket.json, clarifications.json
      acs/run/       the RESUME SET: run.json, requirements.md,
                     requirements-refined.json, baseline.json,
                     handoff-context.md, subject/sources.json and, per step,
                     the files at the step root plus iter-*/verdict.json
      attachments/   only the outside-repo document copies the sender
                     confirmed with --attach
      note.md        the sender's note
      manifest.json  who, when, base, branch, what was withheld, the counters
      trees/<id>     every tree id the state cites (baseline.tree, a
                     verdict's reviewed_sha), so it resolves on the receiver

Absolute paths inside the resume set are rewritten to the tokens in TOKENS on
the way out and back to the receiver's own paths on the way in. Everything
else in the workspace -- iteration audit trails, jobs, agent records, locks,
the lock ledger, session pointers, logs -- stays behind.

Sending changes NOTHING on the sender: no workspace write, no index write, no
ref (user decision, ADR-0131); the only side effects are git objects and the
pushed ref. Receiving lives in `team_handoff_receive`.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile

from ._common import GateError, now_iso, read_json
from . import changes
from .changes import _run_git, current_branch, empty_tree, head_sha
from .repo import find_ticket_partition, repo_dir
from . import run as run_mod

REF_PREFIX = "refs/acs/handoff/"
#: The receiver keeps the fetched commit here, so the trees it cites stay
#: reachable (and never garbage-collected) after the remote ref is deleted.
RECEIVED_PREFIX = "refs/acs/received/"
FORMAT = 1
MANIFEST = "manifest.json"
NOTE = "note.md"

#: Longest-first in practice: the run directory sits inside the repo
#: directory, which (by default) sits inside the checkout.
TOKENS = (("run", "${ACS_RUN_DIR}"), ("repo", "${ACS_REPO_DIR}"),
          ("checkout", "${ACS_CHECKOUT}"))

TICKET_FILES = ("ticket.json", "clarifications.json")
RUN_ROOT_FILES = ("run.json", "requirements.md", "requirements-refined.json",
                  "baseline.json", "handoff-context.md", "subject/sources.json")
#: What never travels, even from a step's root: locks, ledgers, logs, temp files.
_NEVER = re.compile(r"(^lock|\.lock$|\.log$|\.jsonl$|^\.acs-tmp-|^\.)")
_ITER_DIR = re.compile(r"^iter-\d+$")
#: The JSON keys whose values are git object ids the receiver must resolve.
OBJECT_KEYS = ("tree", "reviewed_sha")
_HEX = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")

EXCLUDED_RULES = ("steps/*/iter-*/ (except verdict.json)", "steps/*/<sub-directories>",
                  "jobs/", "agents/", "lock.json", "lock-events.jsonl", "*.log",
                  "sessions/", "subject/ copies not passed with --attach")


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

def handoff_ref(ticket_id):
    return REF_PREFIX + ticket_id


def check_ticket_id(ticket_id, prefix=None):
    """The id, or GateError. It becomes a ref name, so it is held to the
    ticket-id shape rather than trusted."""
    pattern = r"^%s-\d+$" % (re.escape(prefix) if prefix else r"[A-Z][A-Z0-9]*")
    if not ticket_id or not re.match(pattern, ticket_id):
        raise GateError("%r is not a ticket id%s -- a handoff is per TICKET (ADR-0131)"
                        % (ticket_id, " (%s-<n>)" % prefix if prefix else ""))
    return ticket_id


# ---------------------------------------------------------------------------
# Path tokens
# ---------------------------------------------------------------------------

def local_paths(ctx, rdir):
    """{token: this machine's absolute path} for every token that applies."""
    paths = {"run": rdir, "repo": repo_dir(ctx["workspace"], ctx["repo_id"]),
             "checkout": ctx.get("checkout_root")}
    return dict((token, os.path.abspath(paths[name]).rstrip(os.sep))
                for name, token in TOKENS if paths.get(name))


def anchors(ctx, rdir):
    """[(absolute path, token)] for this machine, longest path first -- both
    the spelled and the symlink-resolved form of each."""
    out = set()
    for token, path in local_paths(ctx, rdir).items():
        out.add((path, token))
        out.add((os.path.realpath(path).rstrip(os.sep), token))
    return sorted(out, key=lambda pair: (-len(pair[0]), pair[1]))


def _boundary(text):
    return re.escape(text) + r'(?=[/"\'\s)\]`>,;:]|$)'


def to_tokens(text, pairs):
    for path, token in pairs:
        text = re.sub(_boundary(path), lambda _m, t=token: t, text)
        escaped = json.dumps(path)[1:-1]
        if escaped != path:
            text = re.sub(_boundary(escaped), lambda _m, t=token: t, text)
    return text


def from_tokens(text, paths):
    """Tokens -> this machine's paths (`paths` is local_paths() here)."""
    for token, path in paths.items():
        text = text.replace(token, path)
    return text


# ---------------------------------------------------------------------------
# What is being handed off
# ---------------------------------------------------------------------------

def resolve_subject(ctx, ticket_id):
    """(tdir, run_id, rdir, run_doc) for a ticket's handoff, or GateError.

    Refuses an archived ticket, a missing one, and a run that is not about a
    ticket: the handoff is ticket-level."""
    rpath = repo_dir(ctx["workspace"], ctx["repo_id"])
    direct = run_mod.load_run(run_mod.run_dir(rpath, ticket_id))
    if direct is not None and (direct.get("subject") or {}).get("kind") != "ticket":
        raise GateError("run %s is about a %s, not a ticket -- a handoff hands off a TICKET "
                        "and its run" % (ticket_id, (direct.get("subject") or {}).get("kind")))
    tdir, archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    if archived:
        raise GateError("%s is archived (merged or closed) -- there is nothing to hand off"
                        % ticket_id)
    if not os.path.isfile(os.path.join(tdir, "ticket.json")):
        raise GateError("no ticket %s in this workspace (expected %s)"
                        % (ticket_id, os.path.join(tdir, "ticket.json")))
    rows = run_mod.find_runs_for_subject(rpath, "ticket", ticket_id)
    row = run_mod.latest_open_run(rpath, "ticket", ticket_id) or (rows[-1] if rows else None)
    run_id = row["run_id"] if row else (ticket_id if direct is not None else None)
    if run_id is None:
        return tdir, None, None, None
    rdir = run_mod.run_dir(rpath, run_id)
    doc = run_mod.load_run(rdir)
    if doc is None:
        if os.path.isdir(os.path.join(rpath, "archive", run_id)):
            raise GateError("run %s is archived -- there is nothing to hand off" % run_id)
        return tdir, None, None, None
    return tdir, run_id, rdir, doc


def _walk(base):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            yield os.path.relpath(full, base).replace(os.sep, "/"), full


def _run_file_kept(rel):
    """Is a run-relative path part of the resume set?"""
    if rel in RUN_ROOT_FILES:
        return True
    parts = rel.split("/")
    if parts[0] != run_mod.STEPS_DIRNAME or len(parts) < 3:
        return False
    if len(parts) == 3:
        return not _NEVER.search(parts[2])
    return len(parts) == 4 and bool(_ITER_DIR.match(parts[2])) and parts[3] == "verdict.json"


def resume_set(tdir, rdir):
    """([(package path, absolute path)], [excluded workspace-relative paths])."""
    files, excluded = [], []
    for rel, full in _walk(tdir):
        if rel in TICKET_FILES:
            files.append(("acs/ticket/" + rel, full))
        else:
            excluded.append("ticket/" + rel)
    if rdir:
        for rel, full in _walk(rdir):
            if _run_file_kept(rel):
                files.append(("acs/run/" + rel, full))
            elif not rel.startswith(run_mod.SUBJECT_DIRNAME + "/"):
                excluded.append("run/" + rel)
    return files, excluded


def attachment_candidates(rdir):
    """The outside-repo documents the run copied under subject/ (ADR-0128):
    [{"ref", "name", "copy", "sha256"}]. Each travels only when confirmed."""
    if not rdir:
        return []
    doc = read_json(os.path.join(run_mod.subject_dir(rdir), "sources.json"))
    out = []
    for entry in doc if isinstance(doc, list) else ():
        copy = isinstance(entry, dict) and entry.get("copy")
        if copy:
            out.append({"ref": entry.get("ref"), "name": os.path.basename(copy),
                        "copy": copy, "sha256": entry.get("sha256"),
                        "present": os.path.isfile(copy)})
    return out


def select_attachments(candidates, wanted):
    """The candidates `wanted` names -- by original ref, copy path, run-relative
    `subject/<name>` or bare name. An unknown name is refused: an attachment is
    something the run already holds, never an arbitrary file."""
    chosen = []
    for value in wanted or ():
        match = None
        for cand in candidates:
            keys = {cand["ref"], cand["copy"], cand["name"], "subject/" + cand["name"],
                    os.path.abspath(os.path.expanduser(cand["ref"] or ""))}
            if value in keys or os.path.abspath(os.path.expanduser(value)) in keys:
                match = cand
                break
        if match is None:
            raise GateError("--attach %s is not one of this run's outside-repo attachments "
                            "(%s)" % (value, ", ".join(c["ref"] or c["name"] for c in candidates)
                                      or "it has none"))
        if not match["present"]:
            raise GateError("attachment %s is recorded but its copy %s is missing"
                            % (match["ref"], match["copy"]))
        if match not in chosen:
            chosen.append(match)
    return chosen


def _cited(value, key=None, out=None):
    out = [] if out is None else out
    if isinstance(value, dict):
        for k, v in value.items():
            _cited(v, k, out)
    elif isinstance(value, list):
        for v in value:
            _cited(v, key, out)
    elif key in OBJECT_KEYS and isinstance(value, str) and _HEX.match(value.strip()):
        if value.strip() not in out:
            out.append(value.strip())
    return out


def object_types(root, ids):
    """{id: "tree" | "blob" | "commit" | None} through one cat-file call."""
    if not ids:
        return {}
    proc = subprocess.run(["git", "cat-file", "--batch-check=%(objectname) %(objecttype)"],
                          cwd=root, input="\n".join(ids) + "\n", capture_output=True,
                          text=True)
    found = {i: None for i in ids}
    for line, ident in zip(proc.stdout.splitlines(), ids):
        parts = line.split()
        if len(parts) == 2 and parts[1] in ("tree", "blob", "commit"):
            found[ident] = parts[1]
    return found


# ---------------------------------------------------------------------------
# The package
# ---------------------------------------------------------------------------

def _package_files(files, pairs, chosen):
    """[(package path, bytes)] with absolute paths tokenised; a withheld
    attachment's sources.json entry loses its `copy` and says so."""
    names = {c["name"] for c in chosen}
    out, rewritten = [], []
    for pkg, full in files:
        with open(full, "rb") as handle:
            data = handle.read()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            out.append((pkg, data))
            continue
        if pkg == "acs/run/subject/sources.json":
            entries = json.loads(text) if text.strip() else []
            for entry in entries if isinstance(entries, list) else ():
                if isinstance(entry, dict) and entry.get("copy") and \
                        os.path.basename(entry["copy"]) not in names:
                    entry["copy"] = None
                    entry["handoff_withheld"] = True
            text = json.dumps(entries, indent=2, ensure_ascii=False) + "\n"
        new = to_tokens(text, pairs)
        if new != text:
            rewritten.append(pkg)
        out.append((pkg, new.encode("utf-8")))
    for cand in chosen:
        with open(cand["copy"], "rb") as handle:
            out.append(("attachments/" + cand["name"], handle.read()))
    return out, rewritten


def _identity(root):
    def cfg(key):
        proc = _run_git(root, ["config", "--get", key], check=False)
        return proc.stdout.decode("utf-8", "replace").strip() or None
    return {"name": cfg("user.name"), "email": cfg("user.email")}


def _counters_next(ctx):
    doc = read_json(os.path.join(repo_dir(ctx["workspace"], ctx["repo_id"]), "counters.json"))
    nxt = doc.get("next") if isinstance(doc, dict) else None
    return nxt if isinstance(nxt, int) else None


def plan_send(ctx, ticket_id, attach=()):
    """Everything a send would package, computed without writing anything."""
    root = ctx["checkout_root"]
    check_ticket_id(ticket_id, (ctx.get("settings") or {}).get("ticket_prefix"))
    tdir, run_id, rdir, doc = resolve_subject(ctx, ticket_id)
    files, excluded = resume_set(tdir, rdir)
    candidates = attachment_candidates(rdir)
    chosen = select_attachments(candidates, attach)
    baseline = changes.load_baseline(rdir) if rdir else None
    base = (baseline or {}).get("base_sha") or head_sha(root)
    work = changes.snapshot(root)
    docs = [read_json(full) for pkg, full in files if pkg.endswith(".json")]
    ids = _cited(docs)
    types = object_types(root, ids)
    return {
        "ticket": ticket_id, "run_id": run_id, "tdir": tdir, "rdir": rdir, "run": doc,
        "files": files, "excluded": excluded, "candidates": candidates, "chosen": chosen,
        "base_sha": base, "branch": current_branch(root), "work_tree": work,
        "work_changes": changes.name_status(root, base or empty_tree(root), work),
        "trees": [i for i in ids if types.get(i) in ("tree", "blob")],
        "unresolved_ids": [i for i in ids if types.get(i) not in ("tree", "blob")],
        "object_types": types,
    }


def build_manifest(ctx, plan, rewritten, note):
    candidates, chosen = plan["candidates"], plan["chosen"]
    names = {c["name"] for c in chosen}
    return {
        "format": FORMAT,
        "ticket": plan["ticket"],
        "run_id": plan["run_id"],
        "repo_id": ctx["repo_id"],
        "sender": dict(_identity(ctx["checkout_root"]), checkout_id=ctx.get("checkout_id")),
        "sent_at": now_iso(),
        "base_sha": plan["base_sha"],
        "branch": plan["branch"],
        "work_tree": plan["work_tree"],
        "counters_next": _counters_next(ctx),
        "files": sorted(pkg for pkg, _full in plan["files"]),
        "attachments": [{"ref": c["ref"], "path": "attachments/" + c["name"],
                         "sha256": c["sha256"]} for c in chosen],
        "withheld_attachments": [{"ref": c["ref"], "name": c["name"]}
                                 for c in candidates if c["name"] not in names],
        "trees": list(plan["trees"]),
        "unresolved_ids": list(plan["unresolved_ids"]),
        "path_tokens": dict((token, name) for name, token in TOKENS),
        "rewritten": sorted(rewritten),
        "excluded": list(EXCLUDED_RULES),
        "note": bool((note or "").strip()),
    }


def _ident_env(root):
    """Author/committer for commit-tree when this clone has no identity."""
    proc = _run_git(root, ["var", "GIT_COMMITTER_IDENT"], check=False)
    if proc.returncode == 0:
        return None
    return {"GIT_AUTHOR_NAME": "acs handoff", "GIT_AUTHOR_EMAIL": "acs-handoff@localhost",
            "GIT_COMMITTER_NAME": "acs handoff", "GIT_COMMITTER_EMAIL": "acs-handoff@localhost"}


def build_commit(root, plan, blobs, message):
    """One commit, built through a TEMPORARY index (hash-object, update-index,
    write-tree, commit-tree). The real index, HEAD and refs are untouched."""
    tmpdir = tempfile.mkdtemp(prefix="acs-handoff-")
    try:
        env = {"GIT_INDEX_FILE": os.path.join(tmpdir, "index")}
        _run_git(root, ["read-tree", "--empty"], env=env)
        empty = empty_tree(root)
        if plan["work_tree"] != empty:
            _run_git(root, ["read-tree", "--prefix=work/", plan["work_tree"]], env=env)
        records = []
        for ident in plan["trees"]:
            kind = plan["object_types"].get(ident)
            if kind == "tree" and ident != empty:
                _run_git(root, ["read-tree", "--prefix=trees/%s/" % ident, ident], env=env)
            elif kind == "blob":
                records.append("100644 %s\ttrees/%s" % (ident, ident))
        staged = []
        for n, (pkg, data) in enumerate(blobs):
            path = os.path.join(tmpdir, "b%d" % n)
            with open(path, "wb") as handle:
                handle.write(data)
            staged.append((pkg, path))
        if staged:
            proc = subprocess.run(["git", "hash-object", "-w", "--stdin-paths"], cwd=root,
                                  input="\n".join(p for _pkg, p in staged) + "\n",
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                raise GateError("git hash-object failed: %s" % proc.stderr.strip())
            for (pkg, _path), sha in zip(staged, proc.stdout.split()):
                records.append("100644 %s\t%s" % (sha, pkg))
        if records:
            info = subprocess.run(["git", "update-index", "--add", "-z", "--index-info"],
                                  cwd=root, env=dict(os.environ, **env),
                                  input=("\0".join(records) + "\0").encode("utf-8"),
                                  capture_output=True)
            if info.returncode != 0:
                raise GateError("git update-index failed: %s"
                                % info.stderr.decode("utf-8", "replace").strip())
        tree = _run_git(root, ["write-tree"], env=env).stdout.decode().strip()
        args = ["commit-tree", tree, "-m", message]
        if plan["base_sha"]:
            args += ["-p", plan["base_sha"]]
        return _run_git(root, args, env=_ident_env(root)).stdout.decode().strip()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# The remote
# ---------------------------------------------------------------------------

def remote_ref_sha(root, remote, ref):
    """The sha `ref` names on `remote`, or None. GateError when the remote
    cannot be read at all -- "unreachable" is never reported as "absent"."""
    proc = _run_git(root, ["ls-remote", "--refs", remote, ref], check=False)
    if proc.returncode != 0:
        raise GateError("cannot read %s: %s" % (
            remote, proc.stderr.decode("utf-8", "replace").strip()))
    for line in proc.stdout.decode().splitlines():
        sha, _tab, name = line.partition("\t")
        if name.strip() == ref:
            return sha.strip()
    return None


def push_ref(root, remote, sha, ref, expect):
    """Push `sha` to `ref` with a lease: `expect` None means the ref must not
    exist, a sha means it must still be that one."""
    lease = "--force-with-lease=%s:%s" % (ref, expect or "")
    proc = _run_git(root, ["push", "--quiet", lease, remote, "%s:%s" % (sha, ref)],
                    check=False)
    if proc.returncode != 0:
        raise GateError("pushing %s to %s was refused (it may have changed since it was "
                        "read): %s" % (ref, remote,
                                       proc.stderr.decode("utf-8", "replace").strip()))


def delete_ref(root, remote, ref, expect):
    proc = _run_git(root, ["push", "--quiet", "--force-with-lease=%s:%s" % (ref, expect),
                           remote, ":" + ref], check=False)
    if proc.returncode == 0:
        return True, None
    return False, proc.stderr.decode("utf-8", "replace").strip()


def _message(ticket_id, sender, note):
    who = " ".join(x for x in (sender.get("name"), "<%s>" % sender["email"]
                               if sender.get("email") else None) if x) or "unknown"
    body = (note or "").strip()
    return "acs handoff: %s\n\nfrom %s%s" % (ticket_id, who, "\n\n" + body if body else "")


def send(ctx, ticket_id, note="", attach=(), replace=False, dry_run=False, remote="origin"):
    """Package `ticket_id` and push it to refs/acs/handoff/<ID>. Returns the
    report the CLI prints. Nothing in the workspace or the checkout changes."""
    root = ctx["checkout_root"]
    plan = plan_send(ctx, ticket_id, attach)
    ref = handoff_ref(ticket_id)
    report = {
        "ok": True, "ticket": ticket_id, "run_id": plan["run_id"], "remote": remote,
        "ref": ref, "base_sha": plan["base_sha"], "branch": plan["branch"],
        "work_tree": plan["work_tree"], "work_changes": plan["work_changes"],
        "package": sorted(["work/" + c["path"] for c in plan["work_changes"]
                           if c["status"] != "deleted"]
                          + [pkg for pkg, _f in plan["files"]]
                          + ["attachments/" + c["name"] for c in plan["chosen"]]
                          + [NOTE, MANIFEST]),
        "attachments": [c["ref"] for c in plan["chosen"]],
        "attachments_available": [{"ref": c["ref"], "name": c["name"],
                                   "present": c["present"]} for c in plan["candidates"]],
        "trees": plan["trees"], "unresolved_ids": plan["unresolved_ids"],
        "excluded": plan["excluded"], "dry_run": bool(dry_run),
    }
    if dry_run:
        report.update(commit=None, replaced=False, pushed=False)
        return report
    existing = remote_ref_sha(root, remote, ref)
    if existing and not replace:
        raise GateError("a handoff of %s is already waiting on %s (%s at %s) -- the receiver "
                        "has not picked it up. Pass --replace to overwrite it."
                        % (ticket_id, remote, ref, existing[:12]))
    pairs = anchors(ctx, plan["rdir"])
    blobs, rewritten = _package_files(plan["files"], pairs, plan["chosen"])
    manifest = build_manifest(ctx, plan, rewritten, note)
    blobs.append((NOTE, ((note or "").rstrip() + "\n").encode("utf-8")))
    blobs.append((MANIFEST, (json.dumps(manifest, indent=2, sort_keys=True,
                                        ensure_ascii=False) + "\n").encode("utf-8")))
    sha = build_commit(root, plan, blobs, _message(ticket_id, manifest["sender"], note))
    push_ref(root, remote, sha, ref, existing)
    report.update(commit=sha, replaced=bool(existing), pushed=True,
                  rewritten=manifest["rewritten"], sender=manifest["sender"],
                  withheld_attachments=[w["ref"] for w in manifest["withheld_attachments"]])
    return report


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def read_manifest(root, commit):
    proc = _run_git(root, ["show", "%s:%s" % (commit, MANIFEST)], check=False)
    if proc.returncode != 0:
        return None
    try:
        doc = json.loads(proc.stdout.decode("utf-8"))
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def read_note(root, commit):
    proc = _run_git(root, ["show", "%s:%s" % (commit, NOTE)], check=False)
    return proc.stdout.decode("utf-8", "replace") if proc.returncode == 0 else ""


def fetch_ref(root, remote, ref):
    """Fetch one handoff ref without creating a local ref; returns its sha."""
    proc = _run_git(root, ["fetch", "--quiet", "--no-tags", remote, ref], check=False)
    if proc.returncode != 0:
        raise GateError("cannot fetch %s from %s: %s" % (
            ref, remote, proc.stderr.decode("utf-8", "replace").strip()))
    return _run_git(root, ["rev-parse", "FETCH_HEAD"]).stdout.decode().strip()


def list_waiting(ctx, remote="origin", details=False):
    """The handoffs waiting on `remote`: [{ticket, ref, commit[, sender, sent_at,
    note]}]. `details` fetches each one to read its manifest."""
    root = ctx["checkout_root"]
    proc = _run_git(root, ["ls-remote", "--refs", remote, REF_PREFIX + "*"], check=False)
    if proc.returncode != 0:
        raise GateError("cannot read %s: %s" % (
            remote, proc.stderr.decode("utf-8", "replace").strip()))
    rows = []
    for line in proc.stdout.decode().splitlines():
        sha, _tab, name = line.partition("\t")
        name = name.strip()
        if not name.startswith(REF_PREFIX):
            continue
        row = {"ticket": name[len(REF_PREFIX):], "ref": name, "commit": sha.strip()}
        if details:
            fetch_ref(root, remote, name)
            manifest = read_manifest(root, row["commit"]) or {}
            row.update(sender=manifest.get("sender"), sent_at=manifest.get("sent_at"),
                       branch=manifest.get("branch"),
                       note=read_note(root, row["commit"]).strip())
        rows.append(row)
    rows.sort(key=lambda r: r["ticket"])
    return {"ok": True, "remote": remote, "handoffs": rows, "count": len(rows)}
