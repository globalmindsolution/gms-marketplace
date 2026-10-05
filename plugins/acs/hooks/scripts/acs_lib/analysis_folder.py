"""acs_lib.analysis_folder — an analysis is a FOLDER: a README plus one file per
bounded context (ADR-0133, amending ADR-0114 and ADR-0128).

    analysis/
      README.md            scope and summary, the contexts table, the refined
                           acceptance criteria, cross-cutting risks and
                           decisions, questions and assumptions, the verdict
      order-checkout.md    one bounded context: its impact map, rules and edge
      payment-refunds.md   cases, risks, open questions and API notes

This module owns what makes such a folder well-formed -- the $0 deterministic
checks `record-draft` runs on every draft (ADR-0125) -- and the byte-for-byte
mechanics publication needs: the folder's digest, the copy into the target
folder and the read-back that proves it. It never decides WHERE a folder goes
(`acs_lib.run_docs` / `acs_lib.doc_layout`) or WHEN (`acs_lib.analysis_loop`).

The checks, each a blocking finding of the iteration they run in:

  names        README.md plus kebab-case `.md` context files only: no
               `index.md`, no other casing of README, no subfolder, no other file
  README.md    the full front-matter spec (`front_matter_spec`), its six
               required headings in order, and a `## Contexts` table whose
               links each name a context file of this folder -- every one
               resolving, every context file listed
  context file `context: <its own file stem>` (plus `feature` and the ADR-0122
               version keys on a Discovery run), its five required headings
               in order

The heading and front-matter checks are `structure_lint` and
`front_matter_check` -- the same functions their CLIs run.
"""

import hashlib
import os
import re

#: The folder's name wherever it is published, and its entry file. Never
#: `index.md`: README.md is what a forge renders for a folder.
DIRNAME = "analysis"
README = "README.md"
#: The single file an analysis was before ADR-0133: still READ, never written.
LEGACY_FILENAME = "analysis.md"
#: A context file's name: plain words, kebab-case.
CONTEXT_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\.md$")
#: Names a context file may not take (any casing): the entry file's alternatives.
RESERVED_NAMES = ("readme.md", "index.md")

#: README.md's required headings, in this order.
README_SECTIONS = ("Scope and summary", "Contexts", "Refined acceptance criteria",
                   "Cross-cutting risks and decisions", "Questions and assumptions",
                   "Verdict")
CONTEXTS_HEADING = "Contexts"
#: A context file's required headings, in this order.
CONTEXT_SECTIONS = ("Impact map", "Rules and edge cases", "Risks", "Open questions",
                    "API notes")

#: README.md's front matter: `ticket` on a ticket's run, `feature` on a run
#: with no ticket (ADR-0128) -- plus the ADR-0122 version keys on a Discovery
#: run, whose analysis is the feature's LIVING one. `api_surface` left with
#: ADR-0134 (nothing decides a step on it now); an analysis published earlier
#: still carries it, and a key the spec does not declare is ignored.
FRONT_MATTER_SPEC = "ticket: str; ready_for_planning: bool; needs_design_recommendation: bool"
FEATURE_FRONT_MATTER_SPEC = ("feature: str; ready_for_planning: bool; "
                             "needs_design_recommendation: bool")
DISCOVERY_VERSION_SPEC = ("status: proposed|approved|implemented|deprecated; version: int; "
                          "tickets: list")
#: A context file's front matter: the context it is, and -- on a Discovery
#: run -- the feature and the version keys its README carries.
CONTEXT_FRONT_MATTER_SPEC = "context: str"
DISCOVERY_CONTEXT_FRONT_MATTER_SPEC = ("context: str; feature: str; "
                                       + DISCOVERY_VERSION_SPEC)

#: The slice id the deterministic checks' findings carry in a review.
CHECKS_SLICE = "draft-checks"

_LINK_RE = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_SEPARATOR_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def front_matter_spec(ticket_id, phase=None):
    """README.md's front-matter spec for a run (see FRONT_MATTER_SPEC)."""
    if ticket_id:
        return FRONT_MATTER_SPEC
    if phase == "discovery":
        return FEATURE_FRONT_MATTER_SPEC + "; " + DISCOVERY_VERSION_SPEC
    return FEATURE_FRONT_MATTER_SPEC


def context_front_matter_spec(phase=None):
    """A context file's front-matter spec: the version keys on a run with no
    ticket in Discovery -- exactly when README.md carries them."""
    return DISCOVERY_CONTEXT_FRONT_MATTER_SPEC if phase == "discovery" \
        else CONTEXT_FRONT_MATTER_SPEC


# ---------------------------------------------------------------------------
# Reading a folder
# ---------------------------------------------------------------------------

def is_context_name(name):
    return bool(CONTEXT_NAME_RE.match(name)) and name.lower() not in RESERVED_NAMES


def files(folder):
    """The analysis files in `folder`, by name: README.md first (when present),
    then the context files sorted. Anything else in the folder is not part of
    the analysis (and fails `check_folder`)."""
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    contexts = sorted(n for n in names if is_context_name(n)
                      and os.path.isfile(os.path.join(folder, n)))
    head = [README] if os.path.isfile(os.path.join(folder, README)) else []
    return head + contexts


def entry_folder(path):
    """The analysis folder `path` is the entry file of, else None: a README.md
    whose folder is named `analysis`."""
    if not path or os.path.basename(path) != README:
        return None
    folder = os.path.dirname(path)
    return folder if os.path.basename(folder) == DIRNAME else None


def file_list(path):
    """[absolute paths] of the analysis `path` opens: every file of its folder,
    README first, when `path` is a folder's README.md; `[path]` for a legacy
    single analysis.md; [] for None."""
    if not path:
        return []
    folder = entry_folder(path)
    if folder is None:
        return [path]
    return [os.path.join(folder, name) for name in files(folder)]


def legacy_sibling(entry):
    """The single `analysis.md` a folder's README.md replaces -- the folder's
    parent's `analysis.md` -- or None when `entry` is not a folder's README."""
    folder = entry_folder(entry)
    return os.path.join(os.path.dirname(folder), LEGACY_FILENAME) if folder else None


def existing(entry):
    """The analysis a reader opens for a target README.md: the README when the
    folder has one, else the legacy single file beside the folder, else None."""
    if entry and os.path.isfile(entry):
        return entry
    legacy = legacy_sibling(entry)
    return legacy if legacy and os.path.isfile(legacy) else None


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest(folder):
    """(combined sha256, {name: sha256}, total bytes) over EVERY regular file
    directly in `folder` -- not only the well-named ones, so the bytes the
    checks and the review judged are exactly the bytes publication copies."""
    shas, total = {}, 0
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        names = []
    for name in names:
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            data = handle.read()
        shas[name] = sha256_bytes(data)
        total += len(data)
    combined = sha256_bytes("".join("%s\0%s\n" % (n, shas[n]) for n in sorted(shas))
                            .encode("utf-8"))
    return combined, shas, total


# ---------------------------------------------------------------------------
# The deterministic checks
# ---------------------------------------------------------------------------

def _finding(dimension, name, line, rule, message):
    return {"slice": CHECKS_SLICE, "severity": "blocking", "dimension": dimension,
            "file": "%s/%s" % (DIRNAME, name) if name else DIRNAME,
            "text": "line %d: [%s] %s" % (line, rule, message)}


def _name_findings(folder, names):
    out = []
    for name in names:
        path = os.path.join(folder, name)
        if name == README:
            continue
        if os.path.isdir(path):
            out.append(_finding("structure", name, 0, "unexpected-entry",
                                "%s/ is a folder: an analysis is one flat folder of .md files"
                                % name))
        elif name.lower() == "index.md":
            out.append(_finding("structure", name, 0, "index-file",
                                "the entry file is README.md, never index.md"))
        elif name.lower() == "readme.md":
            out.append(_finding("structure", name, 0, "bad-name",
                                "the entry file is spelled README.md"))
        elif not CONTEXT_NAME_RE.match(name):
            out.append(_finding("structure", name, 0, "bad-name",
                                "%r is not a context file name: plain words in kebab-case "
                                "ending .md (e.g. order-checkout.md)" % name))
    return out


def _section_lines(lines, heading):
    """(first line index, body lines) of the `## <heading>` section, or (None, [])."""
    import markdown_headings  # noqa: E402 -- hooks/scripts is on sys.path
    found = markdown_headings.headings(lines)
    for i, (line_no, level, text) in enumerate(found):
        if text != heading:
            continue
        end = len(lines)
        for nline, nlevel, _t in found[i + 1:]:
            if nlevel <= level:
                end = nline - 1
                break
        return line_no, lines[line_no:end]
    return None, []


def table_links(text):
    """[(line_no, target)] for every link in a data row of the `## Contexts`
    table, plus the line numbers of data rows that link nothing. Returns
    (links, unlinked_rows, has_table)."""
    lines = text.split("\n")
    start, body = _section_lines(lines, CONTEXTS_HEADING)
    if start is None:
        return [], [], False
    links, unlinked, rows, has_table = [], [], 0, False
    in_table, seen_separator = False, False
    for offset, raw in enumerate(body):
        line_no = start + offset + 1
        stripped = raw.strip()
        if not stripped.startswith("|"):
            in_table, seen_separator = False, False
            continue
        if not in_table:
            in_table, seen_separator = True, False
            continue  # the header row
        if not seen_separator and _SEPARATOR_RE.match(stripped):
            seen_separator, has_table = True, True
            continue
        if not seen_separator:
            continue
        rows += 1
        found = _LINK_RE.findall(stripped)
        if not found:
            unlinked.append(line_no)
        links.extend((line_no, target) for target in found)
    return links, unlinked, has_table


def _link_name(target):
    """The context file name a table link names, or None when it leaves the
    folder (a path, a URL, a parent reference)."""
    target = target.split("#", 1)[0]
    if target.startswith("./"):
        target = target[2:]
    if not target or "/" in target or "\\" in target or ":" in target:
        return None
    return target


def _contexts_table(folder, text, contexts):
    out = []
    links, unlinked, has_table = table_links(text)
    if not has_table:
        return [_finding("structure", README, 0, "no-contexts-table",
                         "`## %s` holds no table linking the context files"
                         % CONTEXTS_HEADING)]
    for line_no in unlinked:
        out.append(_finding("structure", README, line_no, "unlinked-row",
                            "a contexts table row links no context file"))
    listed = set()
    for line_no, target in links:
        name = _link_name(target)
        if name is None:
            out.append(_finding("structure", README, line_no, "bad-link",
                                "%r leaves the analysis folder: link a context file by its "
                                "name, e.g. (order-checkout.md)" % target))
        elif name == README or not is_context_name(name):
            out.append(_finding("structure", README, line_no, "bad-link",
                                "%r is not a context file name" % target))
        elif not os.path.isfile(os.path.join(folder, name)):
            out.append(_finding("structure", README, line_no, "broken-link",
                                "%r does not resolve to a file in the analysis folder"
                                % target))
        else:
            listed.add(name)
    if not links and not unlinked:
        out.append(_finding("structure", README, 0, "no-contexts",
                            "the contexts table lists no context"))
    for name in contexts:
        if name not in listed:
            out.append(_finding("structure", README, 0, "unlisted-context",
                                "%s is in the folder but not in the contexts table" % name))
    return out


def _read(folder, name):
    with open(os.path.join(folder, name), encoding="utf-8") as handle:
        return handle.read()


def _lint(dimension, name, findings):
    return [_finding(dimension, name, f.line, f.rule, f.message) for f in findings]


def check_folder(folder, ticket_id=None, phase=None):
    """[finding] for the analysis folder: names, README.md, every context file.
    [] means it is the shape every reader of the analysis was promised."""
    import front_matter_check  # noqa: E402 -- hooks/scripts is on sys.path
    import structure_lint  # noqa: E402
    from . import yamlsubset
    if not os.path.isdir(folder):
        return [_finding("structure", None, 0, "missing-folder",
                         "no analysis folder at %s" % folder)]
    names = sorted(os.listdir(folder))
    findings = _name_findings(folder, names)
    contexts = [n for n in files(folder) if n != README]
    readme_front = None
    if README not in names or not os.path.isfile(os.path.join(folder, README)):
        findings.append(_finding("structure", README, 0, "missing-readme",
                                 "the analysis folder has no README.md"))
    else:
        try:
            text = _read(folder, README)
        except (OSError, UnicodeDecodeError) as exc:
            text = None
            findings.append(_finding("structure", README, 0, "unreadable", str(exc)))
        if text is not None:
            spec = front_matter_check.parse_spec(front_matter_spec(ticket_id, phase))
            findings += _lint("front-matter", README, front_matter_check.check_front_matter(
                text, spec, ticket=ticket_id))
            findings += _lint("structure", README, structure_lint.lint_structure(
                text, list(README_SECTIONS), ordered=True))
            findings += _contexts_table(folder, text, contexts)
            try:
                readme_front, _body = yamlsubset.split_front_matter(text)
            except yamlsubset.YamlSubsetError:
                readme_front = None
    if not contexts:
        findings.append(_finding("structure", None, 0, "no-context-files",
                                 "an analysis holds at least one context file beside "
                                 "README.md"))
    # The context files carry the version keys exactly when the README does.
    spec = front_matter_check.parse_spec(
        context_front_matter_spec(None if ticket_id else phase))
    for name in contexts:
        findings += _check_context(folder, name, spec, readme_front, front_matter_check,
                                   structure_lint)
    return findings


def _check_context(folder, name, spec, readme_front, front_matter_check, structure_lint):
    from . import yamlsubset
    try:
        text = _read(folder, name)
    except (OSError, UnicodeDecodeError) as exc:
        return [_finding("structure", name, 0, "unreadable", str(exc))]
    out = _lint("front-matter", name, front_matter_check.check_front_matter(text, spec))
    try:
        front, _body = yamlsubset.split_front_matter(text)
    except yamlsubset.YamlSubsetError:
        front = None
    stem = name[:-len(".md")]
    if isinstance(front, dict) and isinstance(front.get("context"), str) \
            and front["context"] != stem:
        out.append(_finding("front-matter", name, 1, "context-mismatch",
                            "front matter names context %r; the file is %s (context: %s)"
                            % (front["context"], name, stem)))
    if isinstance(front, dict) and isinstance(readme_front, dict) \
            and isinstance(front.get("feature"), str) \
            and isinstance(readme_front.get("feature"), str) \
            and front["feature"] != readme_front["feature"]:
        out.append(_finding("front-matter", name, 1, "feature-mismatch",
                            "front matter names feature %r; README.md names %r"
                            % (front["feature"], readme_front["feature"])))
    out += _lint("structure", name, structure_lint.lint_structure(
        text, list(CONTEXT_SECTIONS), ordered=True))
    return out


# ---------------------------------------------------------------------------
# Copying a reviewed folder (publication)
# ---------------------------------------------------------------------------

def _refuse_target(target):
    """A reason the folder at `target` may not be published into, or None.
    Publication writes and DELETES inside it, so it must be an `analysis`
    folder that is a real directory (never a symlink out of the tree)."""
    if os.path.basename(os.path.normpath(target)) != DIRNAME:
        return "%s is not an analysis folder (its name must be %r)" % (target, DIRNAME)
    if os.path.islink(target):
        return "%s is a symbolic link; refusing to publish through it" % target
    if os.path.exists(target) and not os.path.isdir(target):
        return "%s exists and is not a folder" % target
    return None


def copy_folder(source, target):
    """Copy every file of the reviewed `source` folder byte-for-byte into
    `target`, read each back, then remove the `.md` files directly in `target`
    that the new analysis no longer has (a context the revision dropped).

    Nothing outside `target` is touched, nor any subfolder or non-`.md` file
    inside it. Returns ({name: sha256} written, [names removed]); raises
    ValueError on a target it must not write into or a copy that reads back
    different bytes."""
    problem = _refuse_target(target)
    if problem:
        raise ValueError(problem)
    _combined, shas, _total = digest(source)
    os.makedirs(target, exist_ok=True)
    for name in sorted(shas):
        with open(os.path.join(source, name), "rb") as handle:
            data = handle.read()
        dest = os.path.join(target, name)
        tmp = dest + ".acs-tmp"
        with open(tmp, "wb") as handle:
            handle.write(data)
        os.replace(tmp, dest)
        with open(dest, "rb") as handle:
            if sha256_bytes(handle.read()) != shas[name]:  # pragma: no cover
                raise ValueError("published bytes at %s differ from the draft" % dest)
    removed = []
    for name in sorted(os.listdir(target)):
        path = os.path.join(target, name)
        if name in shas or not name.endswith(".md") or os.path.isdir(path):
            continue
        os.remove(path)
        removed.append(name)
    return shas, removed


def verify(target, shas):
    """[problem] when the folder at `target` is not exactly the reviewed files
    `shas` ({name: sha256}): a file missing or changed, or a `.md` file the
    review never judged."""
    problems = []
    if not os.path.isdir(target):
        return ["the published analysis folder %s is missing" % target]
    for name in sorted(shas):
        path = os.path.join(target, name)
        if not os.path.isfile(path):
            problems.append("%s is missing" % path)
            continue
        with open(path, "rb") as handle:
            if sha256_bytes(handle.read()) != shas[name]:
                problems.append("%s is not the reviewed bytes" % path)
    for name in sorted(os.listdir(target)):
        if name.endswith(".md") and name not in shas \
                and os.path.isfile(os.path.join(target, name)):
            problems.append("%s was not part of the reviewed analysis"
                            % os.path.join(target, name))
    return problems


def seed(source, target):
    """Start the next iteration's draft folder from this one's files, so the
    next draft pass revises in place. A target that already exists is left
    alone. Returns True when it copied."""
    if os.path.exists(target) or not os.path.isdir(source):
        return False
    os.makedirs(target)
    for name in sorted(os.listdir(source)):
        path = os.path.join(source, name)
        if os.path.isfile(path):
            with open(path, "rb") as src, open(os.path.join(target, name), "wb") as dst:
                dst.write(src.read())
    return True
