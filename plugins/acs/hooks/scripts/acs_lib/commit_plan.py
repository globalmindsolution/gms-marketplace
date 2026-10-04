"""acs_lib.commit_plan — the commits /acs:create-pr proposes, and makes (ADR-0127).

Only `/acs:create-pr` commits. Every step before it leaves its output in the
working tree and records the paths it wrote; this module turns those records,
intersected with the run's changeset (`acs_lib.changes`), into a list of small
reviewable commits the user confirms before anything is staged:

  1. ticket docs     -- `docs/tickets/<ID>/` and what the ticket-docs skills recorded
  2. design docs     -- what create-design / create-data-design / create-flows recorded
  3. per plan slice  -- its tests, then its code (one group when it has one kind)
  4. docs-sync       -- the doc updates docs-sync recorded
  5. e2e suites      -- what create-e2e-tests recorded
  6. other           -- a path some other step recorded

A changed path no step recorded is LEFT OUT and listed; a path that was
already dirty at the run's baseline and has not changed since is EXCLUDED
unless a step recorded it. The plan is deterministic -- the same records and
the same tree give the same plan -- and `execute` commits a (possibly
user-edited) plan with pathspecs only, never `git add -A`.
"""

import os
import posixpath
import re

from ._common import GateError, read_json, slugify
from . import changes, conventions
from .artifacts import TICKETS_PATH
from .derive import execute_reports
from .filemap import load_filemap, normalize_repo_path
from .run import step_dir, steps_dir

LAYERS = ("ticket-docs", "design", "slice", "docs-sync", "e2e", "other")

#: Which layer a step's recorded paths belong to; any other step is `other`.
SKILL_LAYER = {
    "create-ticket": "ticket-docs", "analyze-requirements": "ticket-docs",
    "create-impl-plan": "ticket-docs", "create-api-contract": "ticket-docs",
    "create-test-docs": "ticket-docs",
    "create-design": "design", "create-data-design": "design", "create-flows": "design",
    "code": "slice", "docs-sync": "docs-sync", "create-e2e-tests": "e2e",
}

#: `states` keys that hold a list of written paths. `files` is the one every
#: step records (ADR-0127); the rest are the names steps used before it.
STATE_LIST_KEYS = ("files", "docs_committed", "docs_updated", "suites_written")
#: `states` keys that hold one written path.
STATE_PATH_KEYS = ("plan_path", "contract_path", "design_path")
#: Top-level keys of a step's iteration reports that list written paths.
REPORT_LIST_KEYS = ("files_changed", "repo_files_changed", "docs_committed",
                    "suites_written")
#: Steps whose iteration reports are judgements, not writes.
READ_ONLY_STEPS = ("review-code", "run-e2e-tests", "audit-design", "audit-security")

_TEST_SEGMENTS = {"test", "tests", "__tests__", "spec"}
_TEST_NAME = re.compile(r"(^test_.+\.[^.]+$)|(.+_test\.[^.]+$)|(.+\.(spec|test)\.[^.]+$)")
_DOC_EXTENSIONS = (".md", ".mmd")
_DOC_DIRS = {"docs", "doc"}
_SLICE_REPORT = re.compile(r"^(?:implementer|execute)(?:-([A-Za-z0-9_][A-Za-z0-9_-]{0,39}))?\.json$")


class DocsOnlyRefused(GateError):
    """`--docs` found changed files that are not documents."""

    def __init__(self, non_docs):
        self.non_docs = list(non_docs)
        super().__init__("docs mode commits documents only, and these changed files are "
                         "not documents: %s" % ", ".join(self.non_docs))


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


def doc_set(path):
    """(key, label) of the doc set a document belongs to, for `--docs` mode."""
    if path.startswith(TICKETS_PATH + "/") and path.count("/") >= 3:
        ticket_id = path.split("/")[2]
        return "tickets/%s" % ticket_id, "ticket %s docs" % ticket_id
    parts = [p.lower() for p in path.split("/")]
    dirs, name = parts[:-1], parts[-1]
    if "lld" in dirs:
        rest = parts[dirs.index("lld") + 1:-1]
        feature = rest[0] if rest else None
        return ("lld/%s" % feature, "LLD %s" % feature) if feature else ("lld", "LLD")
    if "hld" in dirs:
        return "hld", "HLD"
    if {"adr", "adrs", "decisions"}.intersection(dirs):
        return "adr", "ADRs"
    if "product" in dirs or "prd" in name or "roadmap" in name:
        return "prd", "PRD"
    if "requirements" in dirs:
        return "requirements", "requirements"
    return "other", "docs"


def _doc_order(key):
    order = ["prd", "requirements", "hld", "lld", "adr", "tickets", "other"]
    head = key.split("/", 1)[0]
    return (order.index(head) if head in order else len(order), key)


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
    if not isinstance(pub, dict):
        return []
    return [p for p in (pub.get("files") or []) if isinstance(p, str)] + \
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
        if rel is None:
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

def _subject(ticket_id, summary):
    if ticket_id:
        return conventions.COMMIT_SUBJECT.format(ticket_id=ticket_id, summary=summary)
    return summary


def proposed_branch(root, ticket=None, fallback_slug="docs"):
    """The branch the commits go on: the current one when it is a feature
    branch, else `<type>/<ticket_id>-<slug>` (or `docs/<slug>` with no ticket)."""
    current = changes.current_branch(root)
    if current and current not in changes.default_branches(root):
        return current
    if ticket:
        return conventions.branch_name(ticket.get("type") or "task", ticket.get("id"),
                                       slugify(ticket.get("title") or ticket.get("id")))
    return "docs/%s" % slugify(fallback_slug)


def _group(gid, subject, layer, paths, **extra):
    doc = {"id": gid, "subject": subject, "layer": layer, "paths": sorted(paths)}
    doc.update(extra)
    return doc


def plan_ticket(root, rdirs, ticket, baseline):
    """The commit plan for one ticket's runs over the changeset since its baseline."""
    ticket_id = ticket.get("id")
    cs = changes.changeset(root, baseline=baseline)
    records = Records(root, ticket_id)
    for rdir in rdirs:
        records.read_run(rdir)
    changed = [e["path"] for e in cs["files"]]
    excluded_paths = [e["path"] for e in cs["excluded"]]
    records.claim_declared(changed)
    # The ticket's own docs folder is the ticket's by construction -- even
    # `ticket.md`, which `--allocate` wrote before the baseline was taken.
    for path in changed + excluded_paths:
        if path.startswith("%s/%s/" % (TICKETS_PATH, ticket_id)):
            records.claim(path, "ticket-docs")
    included = [p for p in changed + excluded_paths if p in records.claims]
    by_layer = {}
    for path in included:
        layer, key = records.claims[path]
        by_layer.setdefault(layer, {}).setdefault(key, []).append(path)
    groups = []
    for summary, layer in (("Add ticket docs", "ticket-docs"), ("Add design docs", "design")):
        if by_layer.get(layer):
            groups.append(_group(layer, _subject(ticket_id, summary), layer,
                                 [p for ps in by_layer[layer].values() for p in ps]))
    for key in sorted(by_layer.get("slice", {}), key=_slice_order):
        paths = by_layer["slice"][key]
        title = records.slice_titles.get(key) or (
            "the integration seams" if key == "integration"
            else "the plan" if key == "main" else "slice %s" % key)
        tests = [p for p in paths if is_test_path(p)]
        code = [p for p in paths if not is_test_path(p)]
        if tests:
            groups.append(_group("slice-%s-tests" % key, _subject(ticket_id, "Add tests for %s"
                                                                  % title),
                                 "slice", tests, slice=key, kind="tests"))
        if code:
            groups.append(_group("slice-%s-code" % key, _subject(ticket_id, "Implement %s"
                                                                 % title),
                                 "slice", code, slice=key, kind="code"))
    for summary, layer in (("Sync docs with the change", "docs-sync"),
                           ("Add e2e suites", "e2e"),
                           ("Add other recorded changes", "other")):
        if by_layer.get(layer):
            groups.append(_group(layer, _subject(ticket_id, summary), layer,
                                 [p for ps in by_layer[layer].values() for p in ps]))
    return {
        "mode": "ticket",
        "ticket_id": ticket_id,
        "branch": proposed_branch(root, ticket),
        "current_branch": changes.current_branch(root),
        "base": baseline.get("base_sha"),
        "tree": cs["tree"],
        "groups": groups,
        "left_out": sorted(p for p in changed if p not in records.claims),
        "excluded": sorted(p for p in excluded_paths if p not in records.claims),
    }


def plan_docs(root, baseline=None):
    """The commit plan for a docs-only change: every uncommitted change since
    the baseline (HEAD when there is none), grouped by doc set. Refuses when a
    changed file is not a document."""
    baseline = baseline or {"base_sha": changes.head_sha(root), "dirty": []}
    cs = changes.changeset(root, baseline=baseline)
    changed = [e["path"] for e in cs["files"]]
    non_docs = sorted(p for p in changed if not is_doc_path(p))
    if non_docs:
        raise DocsOnlyRefused(non_docs)
    sets = {}
    for path in changed:
        key, label = doc_set(path)
        sets.setdefault(key, (label, []))[1].append(path)
    groups = [_group("docs-%s" % key.replace("/", "-"), "Update %s" % sets[key][0], "docs",
                     sets[key][1], doc_set=key)
              for key in sorted(sets, key=_doc_order)]
    return {
        "mode": "docs",
        "ticket_id": None,
        "branch": proposed_branch(root, None, "update " + " ".join(
            sets[k][0] for k in sorted(sets, key=_doc_order)) if sets else "docs"),
        "current_branch": changes.current_branch(root),
        "base": baseline.get("base_sha"),
        "tree": cs["tree"],
        "groups": groups,
        "left_out": [],
        "excluded": sorted(e["path"] for e in cs["excluded"]),
    }


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
