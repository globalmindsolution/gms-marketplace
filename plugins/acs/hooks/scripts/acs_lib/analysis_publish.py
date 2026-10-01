"""acs_lib.analysis_publish — publication of the reviewed analysis (ADR-0114 §5).

Publishing used to be a prose `cp` and `git add`: nothing checked that the
published bytes were the reviewed bytes, or that the commit carried the
ticket's docs folder and nothing else. This is that step as code:

  1. refuse unless the loop's last review passed, and the draft is still the
     exact bytes that review judged (its sha256 was recorded at review time);
  2. run the two deterministic checks (front matter, ordered sections) on the
     draft -- a finding fails the iteration like a judge's blocking finding;
  3. copy the draft byte-for-byte to the resolved analysis path, and read it
     back to prove the copy;
  4. inside the repo, `git add` ONLY the ticket's docs folder and commit ONLY
     that pathspec with `settings.formats.commit_message`. It never pushes:
     /acs:create-pr does.

`record_publication` then re-derives all of it from disk and git before the
loop is `completed`.
"""

import hashlib
import os
import subprocess

from ._common import GateError, now_iso
from .analysis_loop import (_advance, _block, _expect, draft_path,
                            record_check_failure)
from .artifacts import artifact_path, ticket_docs_dir
from .settings import render_format

FRONT_MATTER_SPEC = ("ticket: str; ready_for_planning: bool; api_surface: bool; "
                     "needs_design_recommendation: bool")
SECTIONS = ("Problem restated; Impact map; Questions; Assumptions; Risks; "
            "Refined acceptance criteria; Verdict")
DEFAULT_COMMIT_MESSAGE = "{ticket_id} {summary}"


def run_checks(path, ticket_id):
    """[{dimension, file, text}] from front_matter_check and structure_lint,
    called in-process through the same functions their CLIs use."""
    import front_matter_check  # noqa: E402 -- hooks/scripts is on sys.path
    import structure_lint  # noqa: E402
    findings = []
    for f in front_matter_check.check_file(path, front_matter_check.parse_spec(FRONT_MATTER_SPEC),
                                           ticket=ticket_id):
        findings.append(_check_finding("front-matter", f))
    for f in structure_lint.lint_file(path, structure_lint._parse_sections(SECTIONS),
                                      ordered=True):
        findings.append(_check_finding("structure", f))
    return findings


def _check_finding(dimension, finding):
    return {"slice": "publish-checks", "severity": "blocking", "dimension": dimension,
            "file": "analysis.md",
            "text": "line %d: [%s] %s" % (finding.line, finding.rule, finding.message)}


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
    template = ((settings or {}).get("formats") or {}).get("commit_message") \
        or DEFAULT_COMMIT_MESSAGE
    external = ticket.get("external") if isinstance(ticket.get("external"), dict) else {}
    return render_format(template, {
        "ticket_id": ticket.get("id") or "", "type": ticket.get("type") or "",
        "title": ticket.get("title") or "", "summary": summary,
        "external_key": external.get("key") or ""})


def _reviewed_sha(loop):
    history = loop.get("history") or []
    if not history or not history[-1].get("passed"):
        raise GateError("refusing to publish: the last review did not pass")
    return history[-1].get("draft_sha256")


def publish(rdir, loop, ctx, tdir, ticket, summary=None):
    """Publish the reviewed draft. Returns (loop, report). On a failed check the
    loop moves on (next draft, stalled or capped) and nothing is written."""
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
    findings = run_checks(draft, loop["ticket_id"])
    if findings:
        record_check_failure(loop, findings)
        return loop, {"published": False, "findings": findings,
                      "reason": "%d deterministic check finding(s) on the draft"
                                % len(findings)}
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
        _git(root, "add", "--", docs_dir)
        staged = _git(root, "diff", "--cached", "--quiet", "--", docs_dir, check=False)
        if staged.returncode == 1:
            _git(root, "commit", "-q", "-m", message, "--", docs_dir)
            commit = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
            committed = True
    loop["publication"] = {"path": path, "sha256": _sha(data), "bytes": len(data),
                           "docs_dir": docs_dir, "committed": committed, "commit": commit,
                           "message": message, "verified": False, "at": now_iso()}
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
