"""acs_lib.analysis_publish — publication of the reviewed analysis (ADR-0114 §5, ADR-0127).

Publishing used to be a prose `cp` and `git add`: nothing checked that the
published bytes were the reviewed bytes. This is that step as code:

  1. refuse unless the loop's last review passed, and the draft is still the
     exact bytes that review judged (its sha256 was recorded at review time).
     The two deterministic checks (front matter, ordered sections) ran on
     those bytes when the draft was recorded, and a finding failed that
     iteration's review (`analysis_loop.run_checks`, ADR-0125), so a passed
     review is a clean check;
  2. copy the draft byte-for-byte to the resolved analysis path, and read it
     back to prove the copy;
  3. record the run's docs folder's files as the paths this step wrote. It
     NEVER stages or commits (ADR-0127): only /acs:create-pr commits, and it
     reads these paths to group the ticket docs into their own commit.

The target is resolved by RUN (ADR-0128, `acs_lib.run_docs`), with or without
a ticket: a Development run's analysis goes to
`<development_dir>/<feature>/<ticket-id or run-id>/analysis.md`, a Discovery
run's to the feature's living `<prd_dir>/features/<feature>/analysis.md`. A run
with no feature yet is refused, naming how to record one.

`record_publication` then re-derives it from the working tree before the loop
is `completed`.
"""

import hashlib
import os

from ._common import GateError, now_iso
from .analysis_loop import _advance, _block, _expect, draft_path
from . import run_docs


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _inside(path, folder):
    if not folder:
        return False
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return path == folder or path.startswith(folder + os.sep)


def resolve_target(ctx, rdir):
    """(analysis_path, docs_dir) for the run's analysis. `docs_dir` is the
    run's own Development folder, whose files the step records; a Discovery
    analysis is the feature root's living document and records only itself.
    Refused (GateError) when the run has no feature to file it under."""
    layout = run_docs.run_layout(ctx, rdir)
    target = layout["paths"].get("analysis.md")
    if not target:
        raise GateError(
            "refusing to publish: run %s has no PRD feature to file its analysis under. "
            "Ask the user which feature it belongs to (propose PRD feature slugs with "
            "`acs.py slug`, or a new slug when none fits) and record it with `acs.py "
            "requirements refine` ({\"feature\": \"<slug>\"}), then publish again."
            % (layout.get("run_id") or os.path.basename(rdir)))
    docs_dir = layout["docs_dir"] if layout["phase"] == "development" else None
    return target, docs_dir


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
    path, docs_dir = resolve_target(ctx, rdir)
    root = ctx.get("checkout_root")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".acs-tmp"
    with open(tmp, "wb") as handle:
        handle.write(data)
    os.replace(tmp, path)
    with open(path, "rb") as handle:
        if handle.read() != data:  # pragma: no cover -- a filesystem that lies
            raise GateError("published bytes at %s differ from the draft" % path)
    if root and docs_dir and _inside(path, docs_dir):
        files = _docs_files(root, docs_dir)
    elif root and _inside(path, root):
        files = [os.path.relpath(os.path.realpath(path),
                                 os.path.realpath(root)).replace(os.sep, "/")]
    else:
        files = []
    loop["publication"] = {"path": path, "sha256": _sha(data), "bytes": len(data),
                           "docs_dir": docs_dir, "files": files,
                           "verified": False, "at": now_iso()}
    loop["events"].append({"at": now_iso(), "event": "publish", "detail": path})
    return loop, {"published": True, "publication": loop["publication"]}


def _docs_files(root, docs_dir):
    """Every file in the run's docs folder, repo-relative and sorted: the
    paths this step leaves uncommitted for /acs:create-pr (ADR-0127)."""
    out = []
    real_root = os.path.realpath(root)
    for base, dirs, names in os.walk(docs_dir):
        dirs.sort()
        for name in sorted(names):
            if name.endswith(".acs-tmp"):
                continue
            rel = os.path.relpath(os.path.realpath(os.path.join(base, name)), real_root)
            out.append(rel.replace(os.sep, "/"))
    return sorted(out)


def record_publication(rdir, loop, ctx):
    """Re-derive the publication from the working tree: the published bytes
    are still the reviewed bytes. Nothing is committed, so HEAD is not asked
    (ADR-0127): the working tree is what /acs:create-pr will commit."""
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
    pub["verified"] = True
    _advance(loop, "completed", "record-publication", pub["path"])
    return loop
