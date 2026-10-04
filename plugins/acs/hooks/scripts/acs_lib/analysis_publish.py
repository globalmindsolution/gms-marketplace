"""acs_lib.analysis_publish — publication of the reviewed analysis (ADR-0114 §5).

Publishing used to be a prose `cp` and `git add`: nothing checked that the
published bytes were the reviewed bytes, or that the commit carried the
ticket's docs folder and nothing else. This is that step as code:

  1. refuse unless the loop's last review passed, and the draft is still the
     exact bytes that review judged (its sha256 was recorded at review time).
     The two deterministic checks (front matter, ordered sections) ran on
     those bytes when the draft was recorded, and a finding failed that
     iteration's review (`analysis_loop.run_checks`, ADR-0125), so a passed
     review is a clean check;
  2. copy the draft byte-for-byte to the resolved analysis path, and read it
     back to prove the copy;
  3. inside the repo, `git add` ONLY the ticket's docs folder -- plus the
     low-level design files the ticket's Design runs recorded (`lld_files`) --
     and commit ONLY those pathspecs with `conventions.COMMIT_SUBJECT`. It
     never pushes: /acs:create-pr does.

`record_publication` then re-derives all of it from disk and git before the
loop is `completed`.
"""

import hashlib
import os
import subprocess

from ._common import GateError, now_iso, read_json
from .analysis_loop import _advance, _block, _expect, draft_path
from .artifacts import artifact_path, ticket_docs_dir
from .repo import repo_dir
from .run import run_dir
from .step import result_path
from . import conventions

#: The Design skills whose low-level design documents (`lld/<feature>/...`)
#: are written before the ticket branch exists, and so ride this commit.
LLD_SKILLS = ("create-data-design", "create-flows")


def _git(cwd, *args, check=True):
    proc = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True)
    if check and proc.returncode != 0:
        raise GateError("git %s failed: %s" % (" ".join(args),
                                               proc.stderr.decode("utf-8", "replace").strip()))
    return proc


def _default_branches(root):
    """The repo's default branch names: origin/HEAD's target when the remote
    records one, plus the conventional `main` and `master` either way."""
    names = {"main", "master"}
    ref = _git(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False)
    if ref.returncode == 0:
        names.add(ref.stdout.decode().strip().rsplit("/", 1)[-1])
    return names


def refuse_default_branch(root):
    """acs never commits to the default branch (ADR 0090): the analysis is the
    first commit of the ticket's branch. A detached HEAD has no branch to carry
    the commit at all."""
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.decode().strip()
    if branch == "HEAD":
        raise GateError("refusing to publish: HEAD is detached -- check out the "
                        "ticket's branch first")
    if branch in _default_branches(root):
        raise GateError("refusing to publish on the default branch %r -- acs never "
                        "commits there; check out the ticket's branch first" % branch)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _inside(path, folder):
    if not folder:
        return False
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return path == folder or path.startswith(folder + os.sep)


def resolve_target(ctx, tdir, ticket_id):
    """(analysis_path, docs_dir): the existing resolution -- the first existing
    copy, else the docs folder, else the partition fallback."""
    root = ctx.get("checkout_root")
    return artifact_path(root, tdir, ticket_id, "analysis.md"), ticket_docs_dir(root, ticket_id)


def commit_message(settings, ticket, summary):
    """The subject of the publish commit: `<ticket_id> <summary>` (a script's
    commit cannot ask the repo's style, so it uses the fixed form)."""
    return conventions.COMMIT_SUBJECT.format(
        ticket_id=ticket.get("id") or "", summary=summary)


def _result_dirs(rdir, ctx, ticket_id):
    """The run directories whose step results name this ticket's LLD files:
    the analysis's own run, then the run `step start --ticket` opens for the
    ticket (its id is the ticket id) when that is a different directory."""
    dirs = [rdir]
    if ticket_id and ctx.get("workspace") and ctx.get("repo_id"):
        own = run_dir(repo_dir(ctx["workspace"], ctx["repo_id"]), ticket_id)
        if os.path.realpath(own) != os.path.realpath(rdir):
            dirs.append(own)
    return dirs


def recorded_lld_files(rdir, ctx, ticket_id):
    """The low-level design files the ticket's Design runs wrote, as absolute
    paths, sorted: every `states.files` entry of a COMPLETED
    `steps/<skill>/result.json` for each skill in LLD_SKILLS. An entry is kept
    only when it is an existing file inside the checkout and under an `lld/`
    directory -- a stray path, an escape from the checkout or anything outside
    `lld/` is dropped, never staged."""
    root = ctx.get("checkout_root")
    if not root:
        return []
    found = set()
    for directory in _result_dirs(rdir, ctx, ticket_id):
        for skill in LLD_SKILLS:
            result = read_json(result_path(directory, skill))
            if not isinstance(result, dict) or result.get("status") != "completed":
                continue
            files = (result.get("states") or {}).get("files")
            for entry in files if isinstance(files, list) else ():
                if not isinstance(entry, str) or not entry.strip():
                    continue
                path = os.path.realpath(os.path.join(root, entry))
                rel = os.path.relpath(path, os.path.realpath(root))
                if (_inside(path, root) and os.path.isfile(path)
                        and "lld" in rel.split(os.sep)[:-1]):
                    found.add(path)
    return sorted(found)


def _reviewed_sha(loop):
    history = loop.get("history") or []
    if not history or not history[-1].get("passed"):
        raise GateError("refusing to publish: the last review did not pass")
    return history[-1].get("draft_sha256")


def publish(rdir, loop, ctx, tdir, ticket, summary=None):
    """Publish the reviewed draft. Returns (loop, report)."""
    _expect(loop, "publish")
    draft = draft_path(rdir)
    if not os.path.isfile(draft):
        raise GateError("refusing to publish: no draft at %s" % draft)
    with open(draft, "rb") as handle:
        data = handle.read()
    reviewed = _reviewed_sha(loop)
    if _sha(data) != reviewed:
        raise GateError("refusing to publish: the draft is not the bytes the review passed "
                        "(reviewed %s, now %s)" % ((reviewed or "-")[:12], _sha(data)[:12]))
    path, docs_dir = resolve_target(ctx, tdir, loop["ticket_id"])
    root = ctx.get("checkout_root")
    if root and _inside(path, docs_dir):
        refuse_default_branch(root)  # before anything is written
    existed = os.path.isfile(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".acs-tmp"
    with open(tmp, "wb") as handle:
        handle.write(data)
    os.replace(tmp, path)
    with open(path, "rb") as handle:
        if handle.read() != data:  # pragma: no cover -- a filesystem that lies
            raise GateError("published bytes at %s differ from the draft" % path)
    committed, commit, message = False, None, None
    if root and _inside(path, docs_dir):
        summary = summary or ("Update requirements analysis" if existed
                              else "Add requirements analysis")
        message = commit_message(ctx.get("settings"), ticket, summary)
        lld_files = recorded_lld_files(rdir, ctx, loop.get("ticket_id"))
        pathspecs = [docs_dir] + lld_files
        _git(root, "add", "--", docs_dir)
        if lld_files:
            _git(root, "add", "--", *lld_files)
        staged = _git(root, "diff", "--cached", "--quiet", "--", *pathspecs, check=False)
        if staged.returncode == 1:
            _git(root, "commit", "-q", "-m", message, "--", *pathspecs)
            commit = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
            committed = True
    else:
        lld_files = []
    loop["publication"] = {"path": path, "sha256": _sha(data), "bytes": len(data),
                           "docs_dir": docs_dir, "committed": committed, "commit": commit,
                           "message": message, "verified": False, "at": now_iso(),
                           "lld_files": [os.path.relpath(p, os.path.realpath(root))
                                         for p in lld_files]}
    loop["events"].append({"at": now_iso(), "event": "publish",
                           "detail": "%s%s" % (path, " @ %s" % commit[:12] if commit else "")})
    return loop, {"published": True, "publication": loop["publication"]}


def record_publication(rdir, loop, ctx):
    """Re-derive the publication from disk and git: the published bytes are
    the reviewed bytes, and inside the repo they are what HEAD carries."""
    _expect(loop, "publish")
    pub = loop.get("publication")
    if not pub:
        _block(loop, "machinery", "nothing published yet: run `acs.py analysis publish`")
        return loop
    reviewed = _reviewed_sha(loop)
    if not os.path.isfile(pub["path"]):
        _block(loop, "machinery", "the published analysis %s is missing" % pub["path"])
        return loop
    with open(pub["path"], "rb") as handle:
        data = handle.read()
    if _sha(data) != reviewed:
        _block(loop, "machinery", "the published analysis %s is not the reviewed bytes"
               % pub["path"])
        return loop
    root = ctx.get("checkout_root")
    if root and _inside(pub["path"], pub.get("docs_dir")):
        rel = os.path.relpath(os.path.realpath(pub["path"]), os.path.realpath(root))
        shown = _git(root, "show", "HEAD:%s" % rel.replace(os.sep, "/"), check=False)
        if shown.returncode != 0 or shown.stdout != data:
            _block(loop, "machinery", "HEAD does not carry the published analysis %s" % rel)
            return loop
    pub["verified"] = True
    _advance(loop, "completed", "record-publication", pub["path"])
    return loop
