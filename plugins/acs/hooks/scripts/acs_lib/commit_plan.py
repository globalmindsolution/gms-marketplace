"""acs_lib.commit_plan — the commits /acs:create-pr proposes, and makes (ADR-0127).

Only `/acs:create-pr` commits, and every skill -- create-pr included -- takes
a ticket id, a prompt or a document as its subject. Every step before
create-pr leaves its output in the working tree and records the paths it
wrote; this module turns a run's records, intersected with its changeset
(`acs_lib.changes`), into small reviewable commits the user confirms before
anything is staged (`recorded` mode):

  1. ticket docs     -- what the ticket-docs skills recorded (their phase folders,
                        ADR-0128) and a legacy `docs/tickets/<ID>/`
  2. design docs     -- what create-api-contract / create-data-design /
                        create-flows / create-tech-design recorded
  3. per plan slice  -- its tests, then its code (one group when it has one kind)
  4. docs-sync       -- the doc updates docs-sync recorded
  5. e2e suites      -- what create-e2e-tests recorded
  6. other           -- a path some other step recorded

A run document the user chose to keep LOCAL (ADR-0132) lives in the run's
state folder, not the repo: it is never claimed, grouped or left out.
A changed path no step recorded is LEFT OUT and listed; a path that was
already dirty at the run's baseline and has not changed since is EXCLUDED
unless a step recorded it. A run that recorded nothing (a fresh prompt run, or
work done by hand) is planned in `uncommitted` mode instead: every uncommitted
change against HEAD, documents by doc set, then slices other runs recorded,
then tests and code by path convention. Subjects are `<ticket_id> <summary>`
for a ticket's run and `<summary>` otherwise (`conventions.commit_subject`).
The plan is deterministic, and `execute` commits a (possibly user-edited)
plan with pathspecs only, never `git add -A`.
"""

import os
import posixpath
import re

from ._common import GateError, read_json, slugify
from . import changes, conventions
from .artifacts import TICKETS_PATH
from .derive import execute_reports
from .doc_sets import LLD_LIVING as _LLD_LIVING  # noqa: F401 -- moved, kept importable
from .doc_sets import doc_set, doc_order as _doc_order  # noqa: F401
from .filemap import load_filemap, normalize_repo_path
from .run import step_dir, steps_dir

LAYERS = ("ticket-docs", "design", "slice", "docs-sync", "e2e", "other")

#: Which layer a step's recorded paths belong to; any other step is `other`.
SKILL_LAYER = {
    "create-ticket": "ticket-docs", "breakdown-ticket": "ticket-docs",
    "analyze-requirements": "ticket-docs",
    "create-impl-plan": "ticket-docs", "create-test-docs": "ticket-docs",
    # ADR-0134: the API contract is a Design document, committed with them.
    "create-tech-design": "design", "create-api-contract": "design",
    "create-data-design": "design", "create-flows": "design",
    # Legacy (ADR-0135 renamed it create-tech-design): a run recorded before
    # the rename keeps its design docs in the design layer.
    "create-design": "design",
    "code": "slice", "docs-sync": "docs-sync", "create-e2e-tests": "e2e",
}

#: `states` keys that hold a list of written paths. `files` is the one every
#: step records (ADR-0127); the rest are the names steps used before it.
STATE_LIST_KEYS = ("files", "docs_committed", "docs_updated", "suites_written")
#: `states` keys that hold one written path.
STATE_PATH_KEYS = ("plan_path", "contract_path", "design_path", "tech_design_path")
#: Top-level keys of a step's iteration reports that list written paths.
REPORT_LIST_KEYS = ("files_changed", "repo_files_changed", "docs_committed",
                    "suites_written")
#: Steps whose iteration reports are judgements, not writes.
READ_ONLY_STEPS = ("review-code", "run-e2e-tests", "audit-design", "audit-security")

_TEST_SEGMENTS = {"test", "tests", "__tests__", "spec"}
_TEST_NAME = re.compile(r"(^test_.+\.[^.]+$)|(.+_test\.[^.]+$)|(.+\.(spec|test)\.[^.]+$)")
_DOC_EXTENSIONS = (".md", ".mmd")
#: acs's workspace inside the main checkout (ADR-0086): gitignored state, and
#: where a LOCAL run document is kept (ADR-0132). Never claimed for a commit.
_STATE_ROOT = ".acs/state-machine"
_DOC_DIRS = {"docs", "doc"}
_SLICE_REPORT = re.compile(r"^(?:implementer|execute)(?:-([A-Za-z0-9_][A-Za-z0-9_-]{0,39}))?\.json$")


# ---------------------------------------------------------------------------
# Path classification
# ---------------------------------------------------------------------------

def is_test_path(path):
    """A test file by the common conventions: a `test`/`tests`/`__tests__`/
    `spec` directory segment, or a `test_*.*`, `*_test.*`, `*.spec.*` or
    `*.test.*` file name."""
    parts = path.split("/")
    return bool(_TEST_SEGMENTS.intersection(parts[:-1])) or bool(_TEST_NAME.match(parts[-1]))


def is_doc_path(path):
    """A document: `*.md`, `*.mmd`, or any file under a `docs`/`doc` directory."""
    parts = path.split("/")
    return path.lower().endswith(_DOC_EXTENSIONS) or bool(_DOC_DIRS.intersection(parts[:-1]))


def _in_state_root(rel):
    """Is this repo-relative path acs's own workspace (never committed)?"""
    return rel == _STATE_ROOT or rel.startswith(_STATE_ROOT + "/")


def _rel(root, path):
    """A recorded path as a repo-relative POSIX path, or None when it lies
    outside the checkout."""
    if not isinstance(path, str) or not path.strip():
        return None
    if os.path.isabs(path):
        try:
            path = os.path.relpath(os.path.realpath(path), os.path.realpath(root))
        except ValueError:
            return None
    rel = normalize_repo_path(path)
    return None if not rel or rel.startswith("../") else rel


# ---------------------------------------------------------------------------
# What the run recorded
# ---------------------------------------------------------------------------

def _listdir(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def _states_paths(rdir, skill):
    paths = []
    for doc in (read_json(os.path.join(step_dir(rdir, skill), "state.json")),
                read_json(os.path.join(step_dir(rdir, skill), "result.json"))):
        states = (doc or {}).get("states") if isinstance(doc, dict) else None
        if not isinstance(states, dict):
            continue
        for key in STATE_LIST_KEYS:
            if isinstance(states.get(key), list):
                paths.extend(p for p in states[key] if isinstance(p, str))
        for key in STATE_PATH_KEYS:
            if isinstance(states.get(key), str):
                paths.append(states[key])
    return paths


def _report_paths(rdir, skill):
    paths = []
    sdir = step_dir(rdir, skill)
    for iteration in _listdir(sdir):
        directory = os.path.join(sdir, iteration)
        if not iteration.startswith("iter-") or not os.path.isdir(directory):
            continue
        for name in _listdir(directory):
            doc = read_json(os.path.join(directory, name)) if name.endswith(".json") else None
            if isinstance(doc, dict):
                for key in REPORT_LIST_KEYS:
                    if isinstance(doc.get(key), list):
                        paths.extend(p for p in doc[key] if isinstance(p, str))
    return paths


def _publication_paths(rdir):
    loop = read_json(os.path.join(step_dir(rdir, "analyze-requirements"), "loop.json"))
    pub = (loop or {}).get("publication") if isinstance(loop, dict) else None
    if not isinstance(pub, dict) or pub.get("local"):
        # A LOCAL analysis (ADR-0132) stays in the run's state folder: it is
        # not in the repo, so there is nothing of it to commit.
        return []
    # The analysis is a folder (ADR-0133): its files, and the context files a
    # revision dropped (their deletion is the same documents commit's).
    return [p for p in (pub.get("files") or []) + (pub.get("removed") or [])
            if isinstance(p, str)] + \
        ([pub["path"]] if isinstance(pub.get("path"), str) else [])


def _spec_title(spec):
    name = posixpath.basename(str(spec or ""))
    name = re.sub(r"\.[^.]+$", "", name)
    name = re.sub(r"^\d+[-_]*", "", name)
    return name.replace("-", " ").replace("_", " ").strip() or None


def _slice_order(key):
    if key == "integration":
        return (2, 0, key)
    return (0, int(key), key) if key.isdigit() else (1, 0, key)


class Records:
    """path -> the claim that places it in a group. The first claim in layer
    order wins, so a file two steps touched lands once, in the earlier layer."""

    def __init__(self, root, ticket_id):
        self.root, self.ticket_id, self.claims = root, ticket_id, {}
        self.slice_titles = {}
        #: {slice: [entries]}: the code step's declared file map, every run.
        self.declared = {}

    def claim(self, path, layer, slice_key=None):
        rel = _rel(self.root, path)
        if rel is None or _in_state_root(rel):
            # Outside the checkout, or in acs's own gitignored workspace -- where
            # a document kept LOCAL lives (ADR-0132): never a commit's.
            return
        if self.ticket_id and rel.startswith("%s/%s/" % (TICKETS_PATH, self.ticket_id)):
            layer, slice_key = "ticket-docs", None
        current = self.claims.get(rel)
        if current is None or LAYERS.index(layer) < LAYERS.index(current[0]):
            self.claims[rel] = (layer, slice_key)

    def code_map(self, rdir):
        """{slice: [declared entries]}: the latest file map the guard enforced,
        else the plan's own file map as create-impl-plan recorded it."""
        best = None
        for name in _listdir(step_dir(rdir, "code")):
            match = re.match(r"^iter-(\d+)$", name)
            tasks = load_filemap(rdir, "code", int(match.group(1))) if match else None
            if tasks and (best is None or int(match.group(1)) > best[0]):
                best = (int(match.group(1)), tasks)
        if best:
            return best[1]
        state = read_json(os.path.join(step_dir(rdir, "create-impl-plan"), "state.json")) or {}
        fmap = (state.get("states") or {}).get("file_map") if isinstance(state, dict) else None
        return fmap if isinstance(fmap, dict) else {}

    def read_run(self, rdir):
        for path in _publication_paths(rdir):
            self.claim(path, "ticket-docs")
        for skill in _listdir(steps_dir(rdir)):
            if skill in READ_ONLY_STEPS or not os.path.isdir(step_dir(rdir, skill)):
                continue
            layer = SKILL_LAYER.get(skill, "other")
            if skill == "code":
                self._read_code(rdir)
                continue
            for path in _states_paths(rdir, skill) + _report_paths(rdir, skill):
                self.claim(path, layer)

    def _read_code(self, rdir):
        fmap = {str(k): [normalize_repo_path(f) for f in (v or []) if isinstance(f, str)]
                for k, v in self.code_map(rdir).items() if isinstance(v, list)}
        for _n, path, doc in execute_reports(rdir, "code"):
            match = _SLICE_REPORT.match(os.path.basename(path))
            key = (match.group(1) if match else None) or "main"
            title = _spec_title(doc.get("spec"))
            if title and key not in self.slice_titles:
                self.slice_titles[key] = title
            for changed in doc.get("files_changed") or []:
                self.claim(changed, "slice", key)
        for path in _states_paths(rdir, "code"):
            self.claim(path, "slice", self._slice_of(path, fmap) or "main")
        if os.path.isdir(step_dir(rdir, "code")):
            self.declared.update(fmap)

    def _slice_of(self, path, fmap):
        """The slice whose declared entries cover `path`, or None."""
        rel = _rel(self.root, path) or ""
        for key in sorted(fmap, key=_slice_order):
            if any(rel == e or rel.startswith(e.rstrip("/") + "/") for e in fmap[key] if e):
                return key
        return None

    def claim_declared(self, changed_paths):
        """A changed path inside the code step's declared file map is code's:
        the write guard refused every implementer write outside it."""
        for path in changed_paths:
            key = None if path in self.claims else self._slice_of(path, self.declared)
            if key:
                self.claim(path, "slice", key)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

def subject_of(run_doc, ticket=None):
    """What a plan needs of the run's subject: the ticket id (None for a
    prompt or a document), and the type, id and title its branch is named by."""
    subject = (run_doc or {}).get("subject") or {}
    run_id = (run_doc or {}).get("run_id")
    if ticket:
        return {"run_id": run_id, "ticket_id": ticket.get("id"),
                "type": ticket.get("type") or "task",
                "title": ticket.get("title") or ticket.get("id")}
    title = subject.get("text") or subject.get("path") or run_id or "change"
    return {"run_id": run_id, "ticket_id": None, "type": "task", "title": title}


def proposed_branch(root, subject):
    """The branch the commits go on: the current one when it is a feature
    branch, else `<type>/<ticket_id or run_id>-<slug>` (conventions.BRANCH_FORMAT)."""
    current = changes.current_branch(root)
    if current and current not in changes.default_branches(root):
        return current
    return conventions.branch_name(subject.get("type") or "task",
                                   subject.get("ticket_id") or subject.get("run_id") or "change",
                                   slugify(subject.get("title")))


def _group(gid, subject, layer, paths, **extra):
    doc = {"id": gid, "subject": subject, "layer": layer, "paths": sorted(paths)}
    doc.update(extra)
    return doc


def _by_layer(records, paths):
    by_layer = {}
    for path in paths:
        layer, key = records.claims[path]
        by_layer.setdefault(layer, {}).setdefault(key, []).append(path)
    return by_layer


def _flat(by_key):
    return [p for ps in by_key.values() for p in ps]


def _slice_groups(records, slices, ticket_id):
    """Per slice, its tests then its code (one group when it has one kind)."""
    groups = []
    for key in sorted(slices, key=_slice_order):
        paths = slices[key]
        title = records.slice_titles.get(key) or (
            "the integration seams" if key == "integration"
            else "the plan" if key == "main" else "slice %s" % key)
        tests = [p for p in paths if is_test_path(p)]
        code = [p for p in paths if not is_test_path(p)]
        if tests:
            groups.append(_group("slice-%s-tests" % key, conventions.commit_subject(
                ticket_id, "Add tests for %s" % title), "slice", tests, slice=key, kind="tests"))
        if code:
            groups.append(_group("slice-%s-code" % key, conventions.commit_subject(
                ticket_id, "Implement %s" % title), "slice", code, slice=key, kind="code"))
    return groups


def _envelope(root, subject, mode, base, tree, groups, left_out, excluded):
    return {"mode": mode, "run_id": subject.get("run_id"),
            "ticket_id": subject.get("ticket_id"),
            "branch": proposed_branch(root, subject),
            "current_branch": changes.current_branch(root),
            "base": base, "tree": tree, "groups": groups,
            "left_out": sorted(left_out), "excluded": sorted(excluded)}


def plan(root, rdirs, subject, baseline=None, other_rdirs=()):
    """The commit plan for a run (a ticket's runs) of ANY subject.

    `recorded` mode -- the run's steps recorded what they wrote: those paths,
    intersected with the changeset since the run's baseline, in layers; an
    unrecorded change is left out. `uncommitted` mode -- nothing recorded (a
    fresh prompt run, or work done by hand) or no baseline: every uncommitted
    change against HEAD, grouped by path, with what OTHER runs of this
    checkout recorded used to attribute code to slices. Nothing is refused for
    being a non-document in either mode."""
    records = Records(root, subject.get("ticket_id"))
    for rdir in rdirs:
        records.read_run(rdir)
    if baseline and (records.claims or records.declared):
        return _plan_recorded(root, records, subject, baseline)
    others = Records(root, None)
    for rdir in other_rdirs:
        others.read_run(rdir)
    return _plan_uncommitted(root, others, subject)


def _plan_recorded(root, records, subject, baseline):
    ticket_id = subject.get("ticket_id")
    cs = changes.changeset(root, baseline=baseline)
    changed = [e["path"] for e in cs["files"] if not _in_state_root(e["path"])]
    excluded_paths = [e["path"] for e in cs["excluded"] if not _in_state_root(e["path"])]
    records.claim_declared(changed)
    # The ticket's own docs folder is the ticket's by construction -- even
    # `ticket.md`, which `--allocate` wrote before the baseline was taken.
    if ticket_id:
        for path in changed + excluded_paths:
            if path.startswith("%s/%s/" % (TICKETS_PATH, ticket_id)):
                records.claim(path, "ticket-docs")
    by_layer = _by_layer(records, [p for p in changed + excluded_paths if p in records.claims])
    groups = []
    for summary, layer in (("Add ticket docs", "ticket-docs"), ("Add design docs", "design")):
        if by_layer.get(layer):
            groups.append(_group(layer, conventions.commit_subject(ticket_id, summary), layer,
                                 _flat(by_layer[layer])))
    groups += _slice_groups(records, by_layer.get("slice", {}), ticket_id)
    for summary, layer in (("Sync docs with the change", "docs-sync"),
                           ("Add e2e suites", "e2e"),
                           ("Add other recorded changes", "other")):
        if by_layer.get(layer):
            groups.append(_group(layer, conventions.commit_subject(ticket_id, summary), layer,
                                 _flat(by_layer[layer])))
    return _envelope(root, subject, "recorded", baseline.get("base_sha"), cs["tree"], groups,
                     [p for p in changed if p not in records.claims],
                     [p for p in excluded_paths if p not in records.claims])


def _plan_uncommitted(root, others, subject):
    ticket_id = subject.get("ticket_id")
    base = changes.head_sha(root)
    cs = changes.changeset(root, baseline={"base_sha": base, "dirty": []})
    changed = [e["path"] for e in cs["files"] if not _in_state_root(e["path"])]
    docs = [p for p in changed if is_doc_path(p)]
    rest = [p for p in changed if not is_doc_path(p)]
    sets = {}
    for path in docs:
        key, label = doc_set(path)
        sets.setdefault(key, (label, []))[1].append(path)
    groups = [_group("docs-%s" % key.replace("/", "-"),
                     conventions.commit_subject(ticket_id, "Update %s" % sets[key][0]), "docs",
                     sets[key][1], doc_set=key)
              for key in sorted(sets, key=_doc_order)]
    others.claim_declared(rest)
    by_layer = _by_layer(others, [p for p in rest
                                  if others.claims.get(p, ("",))[0] in ("slice", "e2e")])
    groups += _slice_groups(others, by_layer.get("slice", {}), ticket_id)
    if by_layer.get("e2e"):
        groups.append(_group("e2e", conventions.commit_subject(ticket_id, "Add e2e suites"),
                             "e2e", _flat(by_layer["e2e"])))
    claimed = set(_flat(by_layer.get("slice", {})) + _flat(by_layer.get("e2e", {})))
    tests = [p for p in rest if p not in claimed and is_test_path(p)]
    code = [p for p in rest if p not in claimed and not is_test_path(p)]
    if tests:
        groups.append(_group("tests", conventions.commit_subject(ticket_id, "Add tests"),
                             "tests", tests))
    if code:
        groups.append(_group("code", conventions.commit_subject(ticket_id, "Update code"),
                             "code", code))
    return _envelope(root, subject, "uncommitted", base, cs["tree"], groups, [], [])


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def uncommitted(root):
    """{path} of every uncommitted change: HEAD (or the empty tree) -> now."""
    base = changes.head_sha(root) or changes.empty_tree(root)
    return {e["path"] for e in changes.name_status(root, base, changes.snapshot(root))}


def validate_plan(root, plan):
    """[error, ...] for a plan about to be committed; [] when it may run."""
    errors = []
    if not isinstance(plan, dict):
        return ["the plan is not a JSON object"]
    branch = plan.get("branch")
    if not isinstance(branch, str) or not branch.strip():
        errors.append("the plan names no branch")
    elif branch in changes.default_branches(root):
        errors.append("refusing to commit on the default branch %r -- name a feature "
                      "branch in the plan" % branch)
    else:
        check = changes._run_git(root, ["check-ref-format", "--branch", branch], check=False)
        if check.returncode != 0:
            errors.append("%r is not a valid branch name" % branch)
    groups = plan.get("groups")
    if not isinstance(groups, list) or not groups:
        return errors + ["the plan has no groups to commit"]
    pending = uncommitted(root)
    seen = {}
    for index, group in enumerate(groups):
        gid = (group or {}).get("id") or "#%d" % (index + 1)
        paths = (group or {}).get("paths")
        if not isinstance(group, dict) or not isinstance(group.get("subject"), str) \
                or not group["subject"].strip():
            errors.append("group %s has no subject" % gid)
        if not isinstance(paths, list) or not paths:
            errors.append("group %s is empty" % gid)
            continue
        for path in paths:
            if path in seen:
                errors.append("%s is in both group %s and group %s" % (path, seen[path], gid))
            seen[path] = gid
            if path not in pending:
                errors.append("%s (group %s) is not an uncommitted change" % (path, gid))
    return errors


def _switch(root, branch):
    """Put HEAD on `branch`, carrying the working tree. Returns how."""
    current = changes.current_branch(root)
    if current == branch:
        return "already_on"
    exists = changes._run_git(root, ["rev-parse", "--verify", "--quiet",
                                     "refs/heads/%s" % branch], check=False)
    head = changes.head_sha(root)
    if exists.returncode == 0:
        if exists.stdout.decode().strip() != head:
            raise GateError("branch %r already exists at another commit -- switching to it "
                            "would not carry this working tree; pick another name" % branch)
        changes._run_git(root, ["switch", "-q", branch])
        return "switched"
    if head is None:  # an unborn branch: there is nothing to branch from
        changes._run_git(root, ["symbolic-ref", "HEAD", "refs/heads/%s" % branch])
    else:
        changes._run_git(root, ["switch", "-q", "-c", branch])
    return "created"


def execute(root, plan):
    """Commit `plan`'s groups in order on its branch. Never pushes."""
    errors = validate_plan(root, plan)
    if errors:
        raise GateError("the commit plan cannot run: " + "; ".join(errors))
    how = _switch(root, plan["branch"])
    commits = []
    for group in plan["groups"]:
        paths = list(group["paths"])
        try:
            changes._run_git(root, ["add", "--"] + paths)
            changes._run_git(root, ["commit", "-q", "-m", group["subject"], "--"] + paths)
        except GateError as exc:
            raise GateError("%s -- committed so far: %s" % (
                exc, ", ".join("%s %s" % (c["sha"][:12], c["id"]) for c in commits) or "nothing"))
        commits.append({"id": group.get("id"), "subject": group["subject"],
                        "sha": changes.head_sha(root), "paths": sorted(paths)})
    return {"branch": plan["branch"], "branch_action": how, "commits": commits,
            "remaining": sorted(uncommitted(root))}
